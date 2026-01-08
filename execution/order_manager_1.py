# =============================================================================
# UBICACIÓN: execution/order_manager.py
# DESCRIPCIÓN: ORDER MANAGER V19.7 (TP DECIMAL FIX + ROBUST VALIDATION)
# =============================================================================

import time
import math
import uuid
from execution.director import BinanceOrderDirector

class OrderManager:
    """
    ORDER MANAGER V19.7:
    - Validación T/P Reforzada: Ajuste estricto de decimales.
    - Redondeo a la baja (Floor) para evitar errores de 'insufficient balance'.
    - Reporte de errores de rechazo de Binance.
    """
    def __init__(self, config, api_manager, logger, financials):
        self.cfg = config
        self.api = api_manager
        self.log = logger
        self.fin = financials
        self.director = BinanceOrderDirector(config)
        self.sec = config.ExecutionConfig
        
        # Valores por defecto (se calibran al conectar)
        self.qty_precision = 1     
        self.price_precision = 2   
        self.min_qty = 0.1         
        self._calibrar_precision_con_exchange()

    def _calibrar_precision_con_exchange(self):
        """Obtiene las reglas exactas de decimales del par en Binance."""
        try:
            info = self.api.client.exchange_info()
            for symbol_data in info['symbols']:
                if symbol_data['symbol'] == self.cfg.SYMBOL:
                    for f in symbol_data['filters']:
                        if f['filterType'] == 'LOT_SIZE':
                            step = float(f['stepSize'])
                            # Calcula cuántos decimales permite el par (Ej: 0.1 -> 1 decimal)
                            self.qty_precision = int(round(-math.log(step, 10), 0))
                            self.min_qty = float(f['minQty'])
                        if f['filterType'] == 'PRICE_FILTER':
                            tick = float(f['tickSize'])
                            self.price_precision = int(round(-math.log(tick, 10), 0))
                    break
            self.log.registrar_actividad("OM", f"Calibración: Qty Prec={self.qty_precision}, Min={self.min_qty}")
        except Exception as e: 
            self.log.registrar_error("OM", f"Fallo calibración: {e}")

    def _blindar_float(self, value, precision):
        """
        Corta el número a 'precision' decimales sin redondear hacia arriba.
        Ej: _blindar_float(45.6789, 1) -> 45.6 (NO 45.7)
        Esto evita intentar vender más de lo que se tiene.
        """
        try:
            factor = 10 ** precision
            return math.floor(value * factor) / factor
        except: return value

    def _leer_datos_posicion(self, symbol):
        try:
            raw = self.api.get_position_info(symbol)
            if not raw: return None
            if isinstance(raw, list):
                for p in raw:
                    if p.get('symbol') == symbol: return p
                return raw[0] if len(raw) > 0 else None
            return raw
        except: return None

    def ejecutar_estrategia(self, plan):
        symbol = plan['symbol']
        side = plan['side']
        
        # --- PASO 1: ENTRADA ---
        raw_qty = float(plan['qty'])
        # Ajuste estricto de cantidad de entrada
        qty_blindada = self._blindar_float(raw_qty, self.qty_precision)
        
        if qty_blindada < self.min_qty:
            self.log.registrar_error("OM", f"Cantidad {qty_blindada} menor al mínimo ({self.min_qty})")
            return False, None
            
        plan['qty'] = qty_blindada
        payload_entrada = self.director.construir_entrada(plan)
        ok_entry, resp_entry = self.api.execute_generic_order(payload_entrada)

        if not ok_entry:
            self.log.registrar_error("OM", f"❌ Fallo API Entrada: {resp_entry}")
            return False, None
            
        order_id = resp_entry['orderId']
        self.log.registrar_actividad("OM", f"⏳ Orden enviada ({order_id}). Esperando fill...")
        
        # --- PASO 2 & 3: VERIFICACIÓN ---
        fill_price, filled_qty = self._esperar_llenado_y_verificar_posicion(symbol, order_id, side)
        
        if fill_price == 0:
            self.log.registrar_error("OM", "⚠️ Posición no detectada tras orden. Cancelando...")
            self.api.cancel_order(symbol, order_id)
            return False, None

        plan['entry_price'] = fill_price
        plan['qty'] = filled_qty 
        self.log.registrar_actividad("OM", f"✅ POSICIÓN CONFIRMADA @ {fill_price}")

        # --- PASO 4: STOP LOSS (CRÍTICO) ---
        sl_id = self._colocar_sl_seguro(symbol, side, plan['sl_price'])
        
        if not sl_id:
            self.log.registrar_error("OM", "🚨 CRÍTICO: FALLO SL. CERRANDO POSICIÓN.")
            self.cerrar_posicion(symbol, "EMERGENCY_SL_FAIL")
            return False, None

        # --- PASO 5: TAKE PROFITS (CORREGIDO PARA 1 DECIMAL) ---
        tp_ids = []
        if 'tp_map' in plan:
            self.log.registrar_actividad("OM", f"⚙️ Configurando {len(plan['tp_map'])} TPs...")
            
            for tp in plan['tp_map']:
                # Calculamos cantidad bruta
                raw_tp_qty = filled_qty * tp['qty_pct']
                
                # APLICAMOS EL BLINDAJE DE DECIMALES ESTRICTO
                # Esto asegura que si AAVE usa 1 decimal, enviemos 45.6 y no 45.62
                tp_qty = self._blindar_float(raw_tp_qty, self.qty_precision)
                
                # Validación local
                if tp_qty < self.min_qty:
                    self.log.registrar_error("OM", f"⚠️ TP {tp['id']} Omitido: {tp_qty} < Mínimo {self.min_qty}")
                    continue

                tp_payload = self.director.construir_take_profit_limit(
                    symbol, side, tp_qty, tp['price_target']
                )
                
                # REINTENTO DE COLOCACIÓN
                tp_placed = False
                for i in range(2): 
                    ok_tp, resp_tp = self.api.execute_generic_order(tp_payload)
                    if ok_tp:
                        tp_ids.append(resp_tp['orderId'])
                        self.fin.registrar_orden_en_libro(resp_tp)
                        self.log.registrar_actividad("OM", f"💎 TP {tp['id']} Colocado: {tp_qty} @ {tp['price_target']}")
                        tp_placed = True
                        break
                    else:
                        # Si falla, logueamos el error exacto
                        self.log.registrar_error("OM", f"⚠️ Rechazo TP {tp['id']}: {resp_tp}")
                        time.sleep(0.5)
                
                if not tp_placed:
                    self.log.registrar_error("OM", f"❌ ERROR FINAL: No se pudo colocar TP {tp['id']}")

        # --- PASO 6: REGISTRO ---
        estado_tps = "HARD_TPS_OK" if len(tp_ids) > 0 else "NO_TPS_PLACED"
        
        paquete_completo = {
            'id': str(uuid.uuid4())[:8],
            'symbol': symbol, 'side': side,
            'entry_price': fill_price, 'qty': filled_qty,
            'sl_price': plan['sl_price'], 'sl_order_id': sl_id,
            'tp_order_ids': tp_ids,
            'strategy': plan['strategy'],
            'mode': plan.get('mode', 'UNKNOWN')
        }
        
        self._registrar_en_csv(paquete_completo, estado_tps)
        return True, paquete_completo

    def actualizar_stop_loss(self, symbol, side, new_sl_price):
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
            p_data = self._leer_datos_posicion(symbol)
            if p_data and float(p_data['positionAmt']) != 0:
                amt = float(p_data['positionAmt'])
                side = 'LONG' if amt > 0 else 'SHORT'
                close_side = 'SELL' if side == 'LONG' else 'BUY'
                qty = abs(amt)
                self.api.place_market_order(symbol, close_side, qty, position_side=side)
                self.log.registrar_actividad("OM", f"🏳️ Cierre Total ({reason})")
                return True
        except: return False
        return False

    def reducir_posicion(self, symbol, qty, reason="PARTIAL"):
        try:
            final_qty = self._blindar_float(qty, self.qty_precision)
            p_data = self._leer_datos_posicion(symbol)
            if not p_data: return False
            
            amt = float(p_data['positionAmt'])
            if amt == 0: return False

            side = 'LONG' if amt > 0 else 'SHORT'
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
                    p_data = self._leer_datos_posicion(symbol)
                    if p_data:
                        amt = float(p_data.get('positionAmt', 0))
                        if (side == 'LONG' and amt > 0) or (side == 'SHORT' and amt < 0):
                            return fill_price, fill_qty
            except: pass
            time.sleep(0.5)
        return 0, 0

    def _registrar_en_csv(self, p, tp_status="HARD_TPS"):
        try:
            line = f"{p['id']},{p.get('timestamp', '')},{p['strategy']},{p['side']},{p['entry_price']},{p['qty']},{p['sl_price']},{p['sl_order_id']},{tp_status},OPEN\n"
            with open(self.cfg.FILE_LOG_ORDERS, 'a') as f: f.write(line)
        except: pass

    # --- FUNCIONES MANUALES ---
    def cancelar_orden_especifica(self, symbol, order_id, motivo="MANUAL"):
        try:
            self.api.cancel_order(symbol, order_id)
            self.fin.eliminar_orden_del_libro(order_id)
            self.log.registrar_actividad("OM", f"🗑️ Orden {order_id} cancelada ({motivo}).")
            return True
        except Exception as e:
            self.log.registrar_error("OM", f"Fallo cancelando {order_id}: {e}")
            return False

    def consultar_libro_local(self):
        return self.fin.libro_ordenes_local