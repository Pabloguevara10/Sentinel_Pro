# =============================================================================
# UBICACIÓN: execution/order_manager.py
# DESCRIPCIÓN: ORDER MANAGER V17.1 (BLINDADO V16 + LIBRO LOCAL V17)
# =============================================================================

import time
import math
import uuid
from execution.director import BinanceOrderDirector

class OrderManager:
    """
    ORDER MANAGER V17.1:
    - Lógica de Precisión: V16 (Calibración automática).
    - Lógica de Registro: V17 (Escribe en Libro Local y CSV).
    """
    def __init__(self, config, api_manager, logger, financials):
        self.cfg = config
        self.api = api_manager
        self.log = logger
        self.fin = financials # <--- Inyección V17
        self.director = BinanceOrderDirector(config)
        self.sec = config.ExecutionConfig
        
        # Variables de Precisión (Default seguro)
        self.qty_precision = 3     
        self.price_precision = 2   
        self.min_qty = 0.1         
        self._calibrar_precision_con_exchange()

    def _calibrar_precision_con_exchange(self):
        """Consulta a Binance los decimales exactos permitidos."""
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
        """Ejecuta Entrada -> Polling -> SL + Registro."""
        symbol = plan['symbol']
        side = plan['side']
        
        # 1. Entrada
        # Usamos Director para construir payload, pero aplicamos blindaje local de qty
        raw_qty = float(plan['qty'])
        qty_blindada = self._blindar_float(raw_qty, self.qty_precision)
        
        if qty_blindada < self.min_qty:
            return False, None
            
        plan['qty'] = qty_blindada
        
        # Construcción y Envío
        payload_entrada = self.director.construir_entrada(plan)
        ok_entry, resp_entry = self.api.execute_generic_order(payload_entrada)

        if not ok_entry:
            self.log.registrar_error("OM", f"❌ Fallo Entrada: {resp_entry}")
            return False, None
            
        order_id = resp_entry['orderId']
        
        # 2. Polling
        fill_price, filled_qty = self._esperar_llenado(symbol, order_id)
        if fill_price == 0:
            self.api.cancel_order(symbol, order_id)
            return False, None

        plan['entry_price'] = fill_price
        plan['qty'] = filled_qty
        self.log.registrar_actividad("OM", f"✅ ENTRADA @ {fill_price}")

        # 3. SL + REGISTRO
        sl_id = self._colocar_sl_y_registrar(symbol, side, plan['sl_price'])
        
        if not sl_id:
            self.cerrar_posicion(symbol, "EMERGENCY_NO_SL")
            return False, None
            
        # 4. CSV Completo
        paquete = {
            'id': str(uuid.uuid4())[:8],
            'symbol': symbol, 'side': side,
            'entry_price': fill_price, 'qty': filled_qty,
            'sl_price': plan['sl_price'], 'sl_order_id': sl_id,
            'strategy': plan['strategy'],
            'tp_config': plan.get('tp_map', {})
        }
        self._registrar_en_csv(paquete)
        return True, paquete

    def _colocar_sl_y_registrar(self, symbol, side, sl_price):
        """Coloca SL y escribe en Libro Local."""
        # Blindaje de precio
        sl_price = round(float(sl_price), self.price_precision)
        payload = self.director.construir_stop_loss(symbol, side, sl_price)
        
        for i in range(self.sec.MAX_RETRIES_SL):
            ok, resp = self.api.execute_generic_order(payload)
            if ok:
                sl_id = resp['orderId']
                # REGISTRO V17
                orden_local = {
                    'orderId': sl_id,
                    'symbol': symbol,
                    'side': payload['side'],
                    'type': payload['type'],
                    'stopPrice': sl_price,
                    'positionSide': side,
                    'status': 'NEW'
                }
                self.fin.registrar_orden_en_libro(orden_local)
                self.log.registrar_actividad("OM", f"🛡️ SL @ {sl_price} (ID: {sl_id})")
                return sl_id
            time.sleep(self.sec.RETRY_DELAY)
        return None

    def actualizar_stop_loss(self, symbol, side, new_sl_price):
        """Nuevo -> Registrar -> Borrar Viejo."""
        new_id = self._colocar_sl_y_registrar(symbol, side, new_sl_price)
        if new_id:
            active, _, old_id = self.fin.verificar_si_tiene_sl_local(side)
            if active and str(old_id) != str(new_id):
                self.api.cancel_order(symbol, old_id)
                self.fin.eliminar_orden_del_libro(old_id)
            return new_id
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
        """Soporte para Swing Parciales."""
        try:
            final_qty = self._blindar_float(qty, self.qty_precision)
            # Consultamos lado actual
            pos = self.api.get_position_info(symbol)
            if not pos: return False
            p_data = pos if isinstance(pos, dict) else pos[0] # Seguro simple
            
            side = 'LONG' if float(p_data['positionAmt']) > 0 else 'SHORT'
            close_side = 'SELL' if side == 'LONG' else 'BUY'
            
            # Usamos API directa para mercado
            self.api.place_market_order(symbol, close_side, final_qty, position_side=side, reduce_only=True)
            return True
        except: return False

    def _esperar_llenado(self, symbol, order_id):
        # Mismo polling V16
        for i in range(15):
            try:
                order = self.api.client.query_order(symbol=symbol, orderId=order_id)
                if order['status'] == 'FILLED':
                    return float(order['avgPrice']), float(order['executedQty'])
                if order['status'] in ['CANCELED', 'EXPIRED']: return 0, 0
                time.sleep(0.5)
            except: time.sleep(0.5)
        return 0, 0

    def _registrar_en_csv(self, p):
        try:
            line = f"{p['id']},{p['timestamp']},{p['strategy']},{p['side']},{p['entry_price']},{p['qty']},{p['sl_price']},{p['sl_order_id']},{p.get('tp_config')},OPEN\n"
            with open(self.cfg.FILE_LOG_ORDERS, 'a') as f: f.write(line)
        except: pass