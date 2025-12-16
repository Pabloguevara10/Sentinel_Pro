import csv
import os
from config.config import Config

class Comptroller:
    """
    DEPARTAMENTO DE CONTROL INTERNO (Contralor V11.5 - ANTI-ZOMBIE):
    - Sincroniza con Binance y elimina posiciones fantasma.
    - Actualiza el CSV a 'CERRADA' para evitar resurrecciones al reiniciar.
    """
    def __init__(self, config, order_manager, financials, logger):
        self.cfg = config
        self.om = order_manager
        self.fin = financials 
        self.log = logger
        
        self.posiciones_activas = {} 
        self._recuperar_estado_de_bitacora()

    def aceptar_custodia(self, paquete_posicion):
        pid = paquete_posicion['id']
        paquete_posicion['be_activado'] = False  
        paquete_posicion['ts_activado'] = False  
        paquete_posicion['tp_dinamico_activado'] = False 
        paquete_posicion['pnl_usd'] = 0.0 
        
        self.posiciones_activas[pid] = paquete_posicion
        self.log.registrar_actividad("CONTRALOR", f"🔒 Posición {pid} bajo custodia.")

    def auditar_posiciones(self, current_price, rsi_15m=None):
        if not self.posiciones_activas: return

        for pid, pos in list(self.posiciones_activas.items()):
            pos['current_price'] = current_price
            strategy = pos.get('strategy', 'SNIPER')
            
            if strategy == 'SCALPING_GAMMA':
                self._auditar_gamma(pid, pos, current_price, rsi_15m)
            else:
                self._auditar_sniper(pid, pos, current_price)

    def sincronizar_con_exchange(self):
        """
        Consulta a Binance y mata procesos zombies o actualiza cantidades.
        """
        real_positions = self.om.conn.get_open_positions_info()
        if not real_positions: return

        realidad = {'LONG': 0.0, 'SHORT': 0.0}
        for p in real_positions:
            amt = float(p['positionAmt'])
            if amt > 0: realidad['LONG'] = amt
            elif amt < 0: realidad['SHORT'] = abs(amt)

        for pid, pos in list(self.posiciones_activas.items()):
            side = pos['side']
            qty_local = pos['qty']
            qty_real = realidad.get(side, 0.0)

            # Tolerancia al polvo (Dust < 0.01 se considera 0)
            es_cero_real = qty_real < 0.01

            # CASO 1: Binance dice 0, nosotros tenemos > 0 -> SE CERRÓ
            if es_cero_real and qty_local > 0:
                self.log.registrar_actividad("CONTRALOR", f"🕵️ Auditoría: Posición {pid} cerrada en Binance. Eliminando.")
                self._cerrar_administrativamente(pid, "CIERRE_EXTERNO")
            
            # CASO 2: Cantidades difieren
            elif not es_cero_real and abs(qty_real - qty_local) > 0.1:
                self.log.registrar_actividad("CONTRALOR", f"🕵️ Sincronizando cantidad {pid}: Local={qty_local:.2f} vs Real={qty_real:.2f}")
                pos['qty'] = qty_real

    def _cerrar_administrativamente(self, pid, motivo):
        """Limpia memoria y ACTUALIZA EL CSV para evitar zombies."""
        if pid in self.posiciones_activas:
            del self.posiciones_activas[pid]
            # Actualizar CSV para que no reviva al reiniciar
            self._actualizar_csv_estado(pid, "CERRADA")
            self.log.registrar_actividad("CONTRALOR", f"💀 Posición {pid} cerrada definitivamente ({motivo}). CSV Actualizado.")

    def _actualizar_csv_estado(self, pid_objetivo, nuevo_estado):
        try:
            ruta = self.cfg.FILE_LOG_ORDERS
            if not os.path.exists(ruta): return

            filas_nuevas = []
            encontrado = False
            
            with open(ruta, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    if row['ID_POSICION'] == pid_objetivo:
                        row['ESTADO'] = nuevo_estado
                        encontrado = True
                    filas_nuevas.append(row)
            
            if encontrado:
                with open(ruta, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(filas_nuevas)
        except Exception as e:
            self.log.registrar_error("CONTRALOR", f"Error actualizando CSV: {e}")

    # --- LÓGICAS DE AUDITORÍA ---
    def _auditar_sniper(self, pid, pos, current_price):
        side = pos['side'] 
        entry = pos['entry_price']
        qty = pos['qty']
        diff = (current_price - entry) if side == 'LONG' else (entry - current_price)
        pos['pnl_usd'] = diff * qty 
        roi_pct = diff / entry
        
        if not pos['be_activado'] and roi_pct >= 0.01:
            self._mover_sl(pid, pos, entry, "BE Activado (Sniper)")
            pos['be_activado'] = True
        if roi_pct >= 0.02:
            self._gestionar_trailing_simple(pid, pos, current_price, 0.01)

    def _auditar_gamma(self, pid, pos, current_price, rsi_15m):
        side = pos['side']
        entry = pos['entry_price']
        qty = pos['qty']
        
        diff = (current_price - entry) if side == 'LONG' else (entry - current_price)
        unrealized_pnl = diff * qty
        pos['pnl_usd'] = unrealized_pnl
        
        threshold = getattr(self.cfg.GammaConfig, 'TP_DYNAMIC_THRESHOLD', 150.0)
        
        if not pos['tp_dinamico_activado'] and unrealized_pnl >= threshold:
            qty_pct = getattr(self.cfg.GammaConfig, 'TP_DYNAMIC_QTY_PCT', 0.25)
            qty_to_close = round(qty * qty_pct, 1)
            
            if qty_to_close > 0:
                if self.om.cerrar_posicion_parcial(side, qty_to_close):
                    pos['qty'] -= qty_to_close 
                    pos['tp_dinamico_activado'] = True
                    self._mover_sl(pid, pos, entry, "BE post-TP Dinámico")

        if rsi_15m is not None:
            distancia = getattr(self.cfg.GammaConfig, 'RSI_TRAILING_DIST_NORMAL', 0.03)
            is_extreme = (side == 'LONG' and rsi_15m > 75) or (side == 'SHORT' and rsi_15m < 25)
            if is_extreme:
                distancia = getattr(self.cfg.GammaConfig, 'RSI_TRAILING_DIST_EXTREME', 0.015)
            
            if (diff/entry) > 0.005:
                self._gestionar_trailing_simple(pid, pos, current_price, distancia)

    def _mover_sl(self, pid, pos, new_sl_price, reason):
        if pos['sl_order_id']: self.om.cancelar_orden(pos['sl_order_id'])
        sl_side = 'SELL' if pos['side'] == 'LONG' else 'BUY'
        params_sl = {
            'symbol': self.cfg.SYMBOL, 'side': sl_side, 'type': 'STOP_MARKET',
            'stopPrice': round(new_sl_price, 2), 'positionSide': pos['side'],
            'closePosition': 'true' 
        }
        res = self.om.conn.place_order(params_sl)
        if res and 'orderId' in res:
            pos['sl_order_id'] = res['orderId']
            pos['sl_price'] = new_sl_price
            self.log.registrar_actividad("CONTRALOR", f"🛡️ {reason} -> Nuevo SL: {new_sl_price}")

    def _gestionar_trailing_simple(self, pid, pos, current_price, distancia_pct):
        new_sl = 0.0
        if pos['side'] == 'LONG':
            possible_sl = current_price * (1 - distancia_pct)
            if possible_sl > pos['sl_price']: new_sl = possible_sl
        else: 
            possible_sl = current_price * (1 + distancia_pct)
            if possible_sl < pos['sl_price']: new_sl = possible_sl
        
        if new_sl != 0.0:
            diff = abs(new_sl - pos['sl_price']) / pos['sl_price']
            if diff > 0.002: self._mover_sl(pid, pos, new_sl, "Trailing Update")

    def _recuperar_estado_de_bitacora(self):
        if not os.path.exists(self.cfg.FILE_LOG_ORDERS): return
        try:
            with open(self.cfg.FILE_LOG_ORDERS, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['ESTADO'] == 'ABIERTA':
                        pos = {
                            'id': row['ID_POSICION'],
                            'strategy': row.get('ESTRATEGIA', 'SNIPER'),
                            'side': row['SIDE'],
                            'entry_price': float(row['PRECIO_ENTRADA']),
                            'qty': float(row['QTY']),
                            'sl_price': float(row['SL_PRICE']),
                            'sl_order_id': row.get('SL_ORDER_ID'),
                            'be_activado': False, 'ts_activado': False,
                            'tp_dinamico_activado': False, 'pnl_usd': 0.0
                        }
                        self.posiciones_activas[pos['id']] = pos
                        self.log.registrar_actividad("CONTRALOR", f"♻️ Memoria recuperada: {pos['id']}")
        except Exception: pass
    
    def get_open_positions_count(self): return len(self.posiciones_activas)