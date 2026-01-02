# =============================================================================
# UBICACIÓN: execution/order_manager.py
# DESCRIPCIÓN: ORDER MANAGER V18 (SEGURIDAD BLINDADA + LEGACY SUPPORT)
# =============================================================================

import time
import math
import uuid
from execution.director import BinanceOrderDirector

class OrderManager:
    """
    ORDER MANAGER V18:
    - Protocolo de Seguridad (Entry -> Verify -> Protect).
    - Soporte completo para reducciones parciales (Swing/Gamma TPs).
    """
    def __init__(self, config, api_manager, logger, financials):
        self.cfg = config
        self.api = api_manager
        self.log = logger
        self.fin = financials
        self.director = BinanceOrderDirector(config)
        self.sec = config.ExecutionConfig
        
        self.qty_precision = 1     
        self.price_precision = 2   
        self.min_qty = 0.1         
        self._calibrar_precision_con_exchange()

    def _calibrar_precision_con_exchange(self):
        try:
            info = self.api.client.exchange_info()
            for symbol_data in info['symbols']:
                if symbol_data['symbol'] == self.cfg.SYMBOL:
                    for f in symbol_data['filters']:
                        if f['filterType'] == 'LOT_SIZE':
                            step = float(f['stepSize'])
                            self.qty_precision = int(round(-math.log(step, 10), 0))
                            self.min_qty = float(f['minQty'])
                        if f['filterType'] == 'PRICE_FILTER':
                            tick = float(f['tickSize'])
                            self.price_precision = int(round(-math.log(tick, 10), 0))
                    break
        except Exception: pass

    def _blindar_float(self, value, precision):
        try:
            factor = 10 ** precision
            return math.floor(value * factor) / factor
        except: return value

    def ejecutar_estrategia(self, plan):
        """
        SECUENCIA MAESTRA DE EJECUCIÓN:
        1. Enviar Orden (Market/Limit según Director).
        2. Polling.
        3. Verificar Posición.
        4. Colocar SL y TPs (Hard Orders).
        """
        symbol = plan['symbol']
        side = plan['side']
        
        # --- PASO 1: ENTRADA ---
        raw_qty = float(plan['qty'])
        qty_blindada = self._blindar_float(raw_qty, self.qty_precision)
        
        if qty_blindada < self.min_qty:
            return False, None
            
        plan['qty'] = qty_blindada
        
        payload_entrada = self.director.construir_entrada(plan)
        ok_entry, resp_entry = self.api.execute_generic_order(payload_entrada)

        if not ok_entry:
            self.log.registrar_error("OM", f"❌ Fallo API Entrada: {resp_entry}")
            return False, None
            
        order_id = resp_entry['orderId']
        self.log.registrar_actividad("OM", f"⏳ Orden enviada ({order_id}). Esperando fill...")
        
        # --- PASO 2 & 3: POLLING Y VERIFICACIÓN ---
        fill_price, filled_qty = self._esperar_llenado_y_verificar_posicion(symbol, order_id, side)
        
        if fill_price == 0:
            # Si era Limit y no se llenó, cancelamos y salimos.
            self.api.cancel_order(symbol, order_id)
            return False, None

        plan['entry_price'] = fill_price
        plan['qty'] = filled_qty 
        self.log.registrar_actividad("OM", f"✅ POSICIÓN CONFIRMADA @ {fill_price}")

        # --- PASO 4: PROTECCIÓN (STOP LOSS) ---
        sl_id = self._colocar_sl_seguro(symbol, side, plan['sl_price'])
        
        if not sl_id:
            self.log.registrar_error("OM", "🚨 CRÍTICO: FALLO AL COLOCAR SL. CERRANDO POSICIÓN.")
            self.cerrar_posicion(symbol, "EMERGENCY_SL_FAIL")
            return False, None

        # --- PASO 5: TAKE PROFITS (HARD ORDERS) ---
        tp_ids = []
        if 'tp_map' in plan:
            for tp in plan['tp_map']:
                tp_qty = filled_qty * tp['qty_pct']
                tp_qty = self._blindar_float(tp_qty, self.qty_precision)
                
                if tp_qty >= self.min_qty:
                    tp_payload = self.director.construir_take_profit_limit(
                        symbol, side, tp_qty, tp['price_target']
                    )
                    ok_tp, resp_tp = self.api.execute_generic_order(tp_payload)
                    if ok_tp:
                        tp_ids.append(resp_tp['orderId'])
                        self.fin.registrar_orden_en_libro(resp_tp)

        # --- PASO 6: REGISTRO FINAL ---
        paquete_completo = {
            'id': str(uuid.uuid4())[:8],
            'symbol': symbol, 'side': side,
            'entry_price': fill_price, 'qty': filled_qty,
            'sl_price': plan['sl_price'], 'sl_order_id': sl_id,
            'tp_order_ids': tp_ids,
            'strategy': plan['strategy'],
            'mode': plan.get('mode', 'UNKNOWN')
        }
        
        self._registrar_en_csv(paquete_completo)
        return True, paquete_completo

    def actualizar_stop_loss(self, symbol, side, new_sl_price):
        """Atomic Replacement: Nuevo -> Confirmar -> Borrar Viejo."""
        new_id = self._colocar_sl_seguro(symbol, side, new_sl_price)
        if new_id:
            active, _, old_id = self.fin.verificar_si_tiene_sl_local(side)
            if active and str(old_id) != str(new_id):
                self.api.cancel_order(symbol, old_id)
                self.fin.eliminar_orden_del_libro(old_id)
            return new_id
        return None

    def _colocar_sl_seguro(self, symbol, side, price):
        price = round(float(price), self.price_precision)
        payload = self.director.construir_stop_loss(symbol, side, price)
        
        for i in range(self.sec.MAX_RETRIES_SL):
            ok, resp = self.api.execute_generic_order(payload)
            if ok:
                self.fin.registrar_orden_en_libro(resp)
                self.log.registrar_actividad("OM", f"🛡️ SL Protegido @ {price}")
                return resp['orderId']
            time.sleep(self.sec.RETRY_DELAY)
        return None

    def cerrar_posicion(self, symbol, reason="EXIT"):
        self.api.cancel_all_open_orders(symbol)
        self.fin.sincronizar_libro_con_api()
        try:
            pos = self.api.get_position_info(symbol)
            if pos and float(pos['positionAmt']) != 0:
                side = 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT'
                close_side = 'SELL' if side == 'LONG' else 'BUY'
                qty = abs(float(pos['positionAmt']))
                self.api.place_market_order(symbol, close_side, qty, position_side=side)
                self.log.registrar_actividad("OM", f"🏳️ Cierre Total ({reason})")
                return True
        except: return False
        return False

    def reducir_posicion(self, symbol, qty, reason="PARTIAL"):
        """Soporte para Swing Parciales y Cierres Manuales."""
        try:
            final_qty = self._blindar_float(qty, self.qty_precision)
            pos = self.api.get_position_info(symbol)
            if not pos: return False
            p_data = pos if isinstance(pos, dict) else pos[0]
            
            side = 'LONG' if float(p_data['positionAmt']) > 0 else 'SHORT'
            close_side = 'SELL' if side == 'LONG' else 'BUY'
            
            self.api.place_market_order(symbol, close_side, final_qty, position_side=side, reduce_only=True)
            return True
        except: return False

    def _esperar_llenado_y_verificar_posicion(self, symbol, order_id, side):
        for i in range(15):
            try:
                order = self.api.client.query_order(symbol=symbol, orderId=order_id)
                if order['status'] == 'FILLED':
                    fill_price = float(order['avgPrice'])
                    fill_qty = float(order['executedQty'])
                    
                    pos = self.api.get_position_info(symbol)
                    if pos:
                        amt = float(pos.get('positionAmt', 0))
                        if (side == 'LONG' and amt > 0) or (side == 'SHORT' and amt < 0):
                            return fill_price, fill_qty
            except: pass
            time.sleep(0.5)
        return 0, 0

    def _registrar_en_csv(self, p):
        try:
            line = f"{p['id']},{p.get('timestamp', '')},{p['strategy']},{p['side']},{p['entry_price']},{p['qty']},{p['sl_price']},{p['sl_order_id']},HARD_TPS,OPEN\n"
            with open(self.cfg.FILE_LOG_ORDERS, 'a') as f: f.write(line)
        except: pass