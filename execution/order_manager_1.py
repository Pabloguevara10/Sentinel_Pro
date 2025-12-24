# =============================================================================
# UBICACIÓN: execution/order_manager.py
# DESCRIPCIÓN: ORDER MANAGER V15.14 (CLEANEST PARAMETERS FIX)
# =============================================================================

import time
from binance.error import ClientError

class OrderManager:
    """
    ORDER MANAGER DEFINITIVO (V15.14):
    - Polling: Mantiene la espera de confirmación de entrada.
    - FIX: Eliminado 'workingType' para evitar rechazo 'Algo Order'.
    - FIX: Corregido error lógico de 'closePosition' con órdenes Limit.
    """
    def __init__(self, config, api_manager, logger):
        self.cfg = config
        self.api = api_manager
        self.log = logger

    def ejecutar_estrategia(self, plan):
        """
        Ejecuta Entrada -> Espera Llenado -> Ejecuta SL.
        """
        try:
            symbol = plan['symbol']
            side = plan['side']
            qty = float(plan['qty'])
            
            self.log.registrar_actividad("ORDER_MGR", f"⚡ Iniciando: {side} {symbol} x{qty}")

            # -----------------------------------------------------------
            # PASO 1: ENTRADA A MERCADO
            # -----------------------------------------------------------
            pos_side = 'LONG' if side == 'LONG' else 'SHORT'
            order_side = 'BUY' if side == 'LONG' else 'SELL'
            
            raw_order = self.api.place_market_order(symbol, order_side, qty, position_side=pos_side)
            
            if not raw_order:
                self.log.registrar_error("ORDER_MGR", "❌ Error Crítico: Fallo en orden de entrada.")
                return False, None

            order_id = raw_order['orderId']
            
            # -----------------------------------------------------------
            # PASO 2: BUCLE DE CONFIRMACIÓN (POLLING)
            # -----------------------------------------------------------
            filled_order = self._esperar_llenado_orden(symbol, order_id)
            
            if not filled_order:
                self.log.registrar_error("ORDER_MGR", "❌ Timeout: Entrada no confirmada. Cancelando.")
                self.api.cancel_order(symbol, order_id)
                return False, None

            # -----------------------------------------------------------
            # PASO 3: CÁLCULO DE DATOS
            # -----------------------------------------------------------
            avg_price = float(filled_order.get('avgPrice', 0.0))
            if avg_price == 0.0:
                cumm = float(filled_order.get('cumQuote', 0.0))
                exec_qty = float(filled_order.get('executedQty', 0.0))
                avg_price = cumm / exec_qty if exec_qty > 0 else plan['entry_price']

            plan['entry_price'] = avg_price
            plan['order_id'] = order_id
            plan['timestamp'] = time.time()
            
            self.log.registrar_actividad("ORDER_MGR", f"✅ Ejecución Confirmada @ {avg_price:.2f}")

            # -----------------------------------------------------------
            # PASO 4: STOP LOSS (INTENTO PURO)
            # -----------------------------------------------------------
            sl_price = float(plan['sl_price'])
            
            if self._colocar_sl_con_insistencia(symbol, side, sl_price, qty):
                self.log.registrar_actividad("ORDER_MGR", f"🛡️ SL Asegurado en {sl_price}")
                if hasattr(self.log, 'registrar_orden'):
                    self.log.registrar_orden(plan)
                return True, plan
            else:
                self.log.registrar_error("ORDER_MGR", "🚨 ALERTA: TODOS LOS MÉTODOS DE SL FALLARON.")
                self.log.registrar_error("ORDER_MGR", "⚠️ EJECUTANDO CIERRE DE EMERGENCIA.")
                self.cerrar_posicion(symbol, "EMERGENCY_SL_FAIL")
                return False, None

        except Exception as e:
            self.log.registrar_error("ORDER_MGR", f"Excepción en ejecución: {e}")
            return False, None

    def _esperar_llenado_orden(self, symbol, order_id, timeout=5):
        start = time.time()
        while (time.time() - start) < timeout:
            try:
                order = self.api.client.query_order(symbol=symbol, orderId=order_id)
                status = order.get('status', '')
                if status == 'FILLED': return order
                elif status in ['CANCELED', 'REJECTED', 'EXPIRED']: return None
                time.sleep(0.5) 
            except: time.sleep(1)
        return None

    def actualizar_stop_loss(self, symbol, new_sl_price):
        try:
            pos = self.api.get_position_info(symbol)
            if not pos or float(pos['positionAmt']) == 0: return False
            
            amt = float(pos['positionAmt'])
            qty_real = abs(amt)
            side = 'LONG' if amt > 0 else 'SHORT'
            
            if self._colocar_stop_loss_orden(symbol, side, float(new_sl_price), qty_real):
                try:
                    ops = self.api.client.get_open_orders(symbol=symbol)
                    for o in ops:
                        if o['type'] in ['STOP_MARKET', 'STOP']:
                            stop_p = float(o.get('stopPrice', 0))
                            if abs(stop_p - float(new_sl_price)) / float(new_sl_price) > 0.001:
                                self.api.cancel_order(symbol, o['orderId'])
                except: pass
                return True
            return False
        except: return False

    def _colocar_sl_con_insistencia(self, symbol, side, sl_price, qty):
        intentos = 5
        for i in range(intentos):
            try:
                curr = self.api.get_ticker_price(symbol)
                if (side=='LONG' and curr <= sl_price) or (side=='SHORT' and curr >= sl_price):
                    self.log.registrar_error("ORDER_MGR", "⚠️ Precio cruzó SL. Cancelando.")
                    return False
            except: pass
            
            if self._verificar_orden_existente(symbol, sl_price):
                return True
            
            if self._colocar_stop_loss_orden(symbol, side, sl_price, qty):
                return True
            
            time.sleep(0.5 * (i + 1))
        return False

    def _colocar_stop_loss_orden(self, symbol, side_posicion, sl_price, qty_sl):
        """
        PROTOCOLO LIMPIO: Sin workingType, sin params complejos.
        """
        side_order = 'SELL' if side_posicion == 'LONG' else 'BUY'
        prec = getattr(self.cfg, 'PRICE_PRECISION', 2)
        price_str = "{:0.{}f}".format(sl_price, prec)
        
        # Detectar cierre total
        try:
            pos_info = self.api.get_position_info(symbol)
            pos_amt = float(pos_info['positionAmt']) if pos_info else 0.0
            is_full_close = abs(pos_amt) > 0 and (qty_sl >= (abs(pos_amt) * 0.99))
        except:
            is_full_close = False

        # --- INTENTO 1: STOP_MARKET PURO ---
        try:
            params = {
                'symbol': symbol, 'side': side_order, 'type': 'STOP_MARKET',
                'stopPrice': price_str, 'positionSide': side_posicion
            }
            # Solo agregamos closePosition O quantity. Nunca ambos.
            if is_full_close:
                params['closePosition'] = 'true'
            else:
                params['quantity'] = float(qty_sl)
            
            # NOTA: NO enviamos workingType ni priceProtect.
            if self.api.place_order(params): return True
        except ClientError as e:
            # self.log.registrar_actividad("ORDER_MGR", f"Fallo Market: {e.error_message}")
            pass

        # --- INTENTO 2: STOP LIMIT (FALLBACK) ---
        # Si Market falla, usamos Limit. Limit NUNCA usa closePosition.
        try:
            limit_p = sl_price * (0.95 if side_order == 'SELL' else 1.05)
            limit_str = "{:0.{}f}".format(limit_p, prec)
            
            params = {
                'symbol': symbol, 'side': side_order, 'type': 'STOP',
                'stopPrice': price_str, 'price': limit_str, 
                'quantity': float(qty_sl), # Siempre Qty en Limit
                'positionSide': side_posicion, 'timeInForce': 'GTC'
            }
            if self.api.place_order(params): 
                self.log.registrar_actividad("ORDER_MGR", "✅ SL (Limit) Activado.")
                return True
        except Exception as e:
            self.log.registrar_error("ORDER_MGR", f"❌ Fallo SL Final: {e}")

        return False

    def _verificar_orden_existente(self, symbol, price):
        try:
            orders = self.api.client.get_open_orders(symbol=symbol)
            for o in orders:
                if o['type'] in ['STOP_MARKET', 'STOP']:
                    stop_p = float(o.get('stopPrice', 0))
                    if abs(stop_p - price) < (price * 0.0005): return True
            return False
        except: return False

    def cerrar_posicion(self, symbol, reason="EXIT"):
        try:
            self.api.cancel_all_open_orders(symbol)
            pos = self.api.get_position_info(symbol)
            if not pos or float(pos['positionAmt'])==0: return True
            qty = abs(float(pos['positionAmt']))
            side = 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT'
            side_close = 'SELL' if side == 'LONG' else 'BUY'
            self.api.place_market_order(symbol, side_close, qty, position_side=side)
            return True
        except: return False
        
    def reducir_posicion(self, symbol, qty, reason="PARTIAL"):
        try:
            pos = self.api.get_position_info(symbol)
            if not pos or float(pos['positionAmt'])==0: return False
            side = 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT'
            side_close = 'SELL' if side == 'LONG' else 'BUY'
            self.api.place_market_order(symbol, side_close, qty, position_side=side)
            return True
        except: return False