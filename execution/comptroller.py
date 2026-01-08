# =============================================================================
# UBICACIÓN: execution/comptroller.py
# DESCRIPCIÓN: CONTRALOR V19.4 (HEDGE FIX FOR ORPHANS + BLACKBOX)
# =============================================================================

from config.config import Config
try:
    from logs.system_logger import SystemLogger
except ImportError:
    SystemLogger = None

class Comptroller:
    def __init__(self, config, order_manager, financials, logger, evaluator=None):
        self.cfg = config
        self.om = order_manager
        self.fin = financials
        self.log = logger
        self.eval = evaluator 
        self.posiciones_activas = {} 

    def aceptar_custodia(self, paquete_orden):
        symbol = paquete_orden['symbol']
        key = f"{symbol}_{paquete_orden['side']}"
        
        # Inicializar métricas
        paquete_orden['max_price'] = paquete_orden['entry_price'] 
        paquete_orden['min_price'] = paquete_orden['entry_price']
        paquete_orden['be_triggered'] = False
        paquete_orden['tp1_hit'] = False 
        
        self.posiciones_activas[key] = paquete_orden
        if self.log: self.log.registrar_actividad("COMP", f"🛡️ Custodia iniciada: {key}")

    def auditar_posiciones(self, current_price):
        if not self.posiciones_activas: return

        for key, pos in list(self.posiciones_activas.items()):
            pos['current_price'] = current_price
            side = pos['side']
            entry = float(pos['entry_price'])
            
            # Actualizar High/Low locales
            if current_price > pos['max_price']: pos['max_price'] = current_price
            if current_price < pos['min_price']: pos['min_price'] = current_price

            # PnL %
            if side == 'LONG': pnl_pct = (current_price - entry) / entry
            else: pnl_pct = (entry - current_price) / entry
            
            pos['pnl_pct'] = pnl_pct

            # Verificar SL actualizado
            tiene_sl, sl_real, _ = self.fin.verificar_si_tiene_sl_local(side)
            if tiene_sl: pos['sl_price'] = sl_real

            # ROUTING DE ESTRATEGIA
            strategy = pos.get('strategy', 'MANUAL')
            
            if strategy == 'GAMMA' or strategy == 'RECOVERY':
                self._gestion_gamma_v4_6(pos, current_price, pnl_pct)
            elif strategy == 'SWING':
                self._gestion_swing(pos, current_price, pnl_pct)
            elif strategy == 'SHADOW':
                self._gestion_shadow(pos, current_price, pnl_pct)

    def adoptar_posiciones_huerfanas(self):
        """
        Recuperación tras reinicio (Versión V19.4 - Hedge Fixed):
        """
        try:
            pos_info = self.om.api.get_position_info(self.cfg.SYMBOL)
            if not pos_info: return
            if isinstance(pos_info, dict): pos_info = [pos_info]

            for p in pos_info:
                amt = float(p['positionAmt'])
                if amt == 0: continue
                
                side = 'LONG' if amt > 0 else 'SHORT'
                key = f"{self.cfg.SYMBOL}_{side}"
                entry_price = float(p['entryPrice'])

                if key in self.posiciones_activas: continue

                self.log.registrar_actividad("COMP", f"🚑 Adoptando Huérfana: {side} @ {entry_price}")
                
                has_sl = False
                existing_tps = 0
                
                try:
                    orders = self.om.api.client.get_open_orders(symbol=self.cfg.SYMBOL)
                    if orders:
                        exit_side = 'SELL' if side == 'LONG' else 'BUY'
                        for o in orders:
                            if o['side'] == exit_side:
                                if o['type'] in ['STOP_MARKET', 'STOP']: has_sl = True
                                if o['type'] == 'LIMIT': existing_tps += 1
                except Exception as e:
                    self.log.registrar_error("COMP", f"⚠️ Fallo leyendo órdenes abiertas ({str(e)}). Asumiendo SIN protección.")
                    has_sl = False
                    existing_tps = 0

                # A. SL de Emergencia
                sl_id = "UNKNOWN"
                if not has_sl:
                    self.log.registrar_error("COMP", f"⚠️ Posición {side} SIN SL detectado. Creando protección...")
                    sl_pct = self.cfg.GammaConfig.SL_NORMAL
                    sl_price = entry_price * (1 - sl_pct) if side == 'LONG' else entry_price * (1 + sl_pct)
                    sl_id = self.om._colocar_sl_seguro(self.cfg.SYMBOL, side, sl_price)
                    if not sl_id: sl_id = "FAILED"
                else:
                    self.log.registrar_actividad("COMP", f"✅ SL detectado en exchange.")

                # B. Restauración de TPs (CON PARCHE HEDGE)
                tp_ids = []
                if existing_tps == 0:
                    self.log.registrar_actividad("COMP", f"🔧 Restaurando TPs LIMIT en el libro...")
                    
                    cfg = self.cfg.GammaConfig
                    qty_total = abs(amt)
                    
                    tp1_dist = cfg.TP_1_DIST
                    tp1_qty = qty_total * cfg.TP_1_QTY
                    tp1_price = entry_price * (1 + tp1_dist) if side == 'LONG' else entry_price * (1 - tp1_dist)
                    
                    tp2_dist = cfg.TP_2_DIST
                    tp2_qty = qty_total * cfg.TP_2_QTY
                    tp2_price = entry_price * (1 + tp2_dist) if side == 'LONG' else entry_price * (1 - tp2_dist)
                    
                    # --- TP1 ---
                    tp1_payload = self.om.director.construir_take_profit_limit(
                        self.cfg.SYMBOL, side, self.om._blindar_float(tp1_qty, self.om.qty_precision), tp1_price
                    )
                    # PARCHE HEDGE MODE
                    if 'reduceOnly' in tp1_payload: del tp1_payload['reduceOnly']
                    tp1_payload['positionSide'] = side

                    ok1, res1 = self.om.api.execute_generic_order(tp1_payload)
                    if ok1: 
                        tp_ids.append(res1['orderId'])
                        self.log.registrar_actividad("COMP", f"💎 TP1 Recuperado: {tp1_price}")
                    else:
                        self.log.registrar_error("COMP", f"❌ Fallo TP1 Recuperación: {res1}")

                    # --- TP2 ---
                    tp2_payload = self.om.director.construir_take_profit_limit(
                        self.cfg.SYMBOL, side, self.om._blindar_float(tp2_qty, self.om.qty_precision), tp2_price
                    )
                    # PARCHE HEDGE MODE
                    if 'reduceOnly' in tp2_payload: del tp2_payload['reduceOnly']
                    tp2_payload['positionSide'] = side

                    ok2, res2 = self.om.api.execute_generic_order(tp2_payload)
                    if ok2: 
                        tp_ids.append(res2['orderId'])
                        self.log.registrar_actividad("COMP", f"💎 TP2 Recuperado: {tp2_price}")
                    else:
                        self.log.registrar_error("COMP", f"❌ Fallo TP2 Recuperación: {res2}")
                else:
                    self.log.registrar_actividad("COMP", f"✅ {existing_tps} TPs (Limit) detectados en libro.")

                paquete = {
                    'symbol': self.cfg.SYMBOL, 'side': side, 'qty': abs(amt),
                    'entry_price': entry_price, 'strategy': 'RECOVERY',
                    'sl_order_id': sl_id, 'tp_order_ids': tp_ids,
                    'mode': 'HEDGE',
                    'max_price': entry_price, 'min_price': entry_price,
                    'be_triggered': False, 'tp1_hit': False
                }
                self.posiciones_activas[key] = paquete
                self.log.registrar_actividad("COMP", f"🛡️ Custodia restaurada y blindada para {key}")

        except Exception as e:
            self.log.registrar_error("COMP", f"❌ ERROR CRÍTICO ADOPCIÓN: {str(e)}")

    def _gestion_gamma_v4_6(self, pos, curr, pnl_pct):
        cfg = self.cfg.GammaConfig
        if not pos['be_triggered']:
            if pnl_pct >= cfg.BE_ACTIVATION:
                if pos['side'] == 'LONG': nuevo_sl = pos['entry_price'] * (1 + cfg.BE_PROFIT)
                else: nuevo_sl = pos['entry_price'] * (1 - cfg.BE_PROFIT)
                self._mover_sl(pos, nuevo_sl)
                pos['be_triggered'] = True
                if self.log: self.log.registrar_actividad("COMP", "🔓 Break Even Activado (+0.5% Asegurado)")

        if pos['be_triggered']:
            distancia = cfg.TRAILING_DIST
            if pos['side'] == 'LONG':
                propuesto = curr * (1 - distancia)
                if propuesto > pos['sl_price']: self._mover_sl(pos, propuesto)
            else:
                propuesto = curr * (1 + distancia)
                if propuesto < pos['sl_price']: self._mover_sl(pos, propuesto)

    def _gestion_swing(self, pos, curr, pnl_pct):
        cfg = self.cfg.SwingConfig
        if not pos['tp1_hit'] and pnl_pct >= cfg.TP1_DIST:
            qty_total = float(pos['qty'])
            qty_close = qty_total * cfg.TP1_QTY_PCT
            if self.log: self.log.registrar_actividad("COMP", f"⭐ TP1 SWING alcanzado. Cerrando {qty_close:.3f}")
            if self.om.reducir_posicion(pos['symbol'], qty_close, "TP1_SWING"):
                pos['qty'] -= qty_close
                pos['tp1_hit'] = True
                self._mover_sl(pos, pos['entry_price'])

    def _gestion_shadow(self, pos, curr, pnl_pct):
        pass

    def _mover_sl(self, pos, nuevo_precio):
        if abs(nuevo_precio - pos.get('sl_price', 0)) / (pos.get('sl_price', 1)) < 0.001: return
        exito = self.om.actualizar_stop_loss(pos['symbol'], pos['side'], nuevo_precio)
        if exito: pos['sl_price'] = nuevo_precio

    def sincronizar_con_exchange(self):
        try:
            real_positions = self.fin.obtener_posiciones_activas_simple()
            real_keys = set(f"{p['symbol']}_{p['side']}" for p in real_positions)
            
            keys_to_delete = [k for k in self.posiciones_activas if k not in real_keys]
            
            for k in keys_to_delete:
                if self.eval:
                    pos_data = self.posiciones_activas[k]
                    last_price = pos_data.get('current_price', pos_data['entry_price'])
                    last_pnl = pos_data.get('pnl_pct', 0.0)
                    self.eval.registrar_salida(
                        trade_id=pos_data.get('id', 'UNKNOWN'),
                        close_price=last_price,
                        pnl_pct=last_pnl,
                        reason="EXCHANGE_CLOSED"
                    )

                del self.posiciones_activas[k]
                if self.log: self.log.registrar_actividad("COMP", f"🏳️ Posición Finalizada: {k}")
        except Exception: pass