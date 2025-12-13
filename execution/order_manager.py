import uuid
import time
from config.config import Config

class OrderManager:
    """
    DEPARTAMENTO DE OPERACIONES (Ejecución):
    Encargado de transformar un 'Plan de Tiro' en órdenes reales en el Exchange.
    VERSION: 8.3 (Fix de parámetros closePosition)
    """
    def __init__(self, config, api_conn, logger):
        self.cfg = config
        self.conn = api_conn
        self.log = logger

    def ejecutar_estrategia(self, plan):
        self.log.registrar_actividad("ORDER_MANAGER", f"🔫 Iniciando ejecución: {plan['strategy']} ({plan['side']})")

        # 1. EJECUCIÓN DE ENTRADA (MARKET)
        qty_final = self._redondear_cantidad(plan['qty'])
        
        params_entry = {
            'symbol': self.cfg.SYMBOL,
            'side': plan['side'], 
            'type': 'MARKET',
            'quantity': qty_final,
            'positionSide': plan['side'] 
        }

        res_entry = self.conn.place_order(params_entry)
        
        if not res_entry or 'orderId' not in res_entry:
            self.log.registrar_error("ORDER_MANAGER", f"Fallo en Entrada: {res_entry}")
            return False, None

        real_entry_price = self.conn.get_ticker_price(self.cfg.SYMBOL) 
        entry_order_id = res_entry['orderId']
        pos_id = str(uuid.uuid4())[:8] 

        self.log.registrar_actividad("ORDER_MANAGER", f"✅ Entrada Confirmada (ID: {entry_order_id}). Precio aprox: {real_entry_price}")

        # 2. COLOCACIÓN DE STOP LOSS (CRÍTICO)
        sl_side = 'SELL' if plan['side'] == 'BUY' else 'BUY'
        sl_price = self._redondear_precio(plan['sl_price'])
        
        # FIX: Si usamos closePosition=True, NO enviamos quantity
        params_sl = {
            'symbol': self.cfg.SYMBOL,
            'side': sl_side,
            'type': 'STOP_MARKET',
            'stopPrice': sl_price,
            'positionSide': plan['side'],
            'timeInForce': 'GTC',
            'closePosition': 'true' 
        }
        # Nota: Eliminamos 'quantity' de aquí porque closePosition tiene prioridad

        res_sl = self.conn.place_order(params_sl)
        
        if not res_sl:
            self.log.registrar_error("ORDER_MANAGER", "🚨 FALLO CRÍTICO EN SL. CERRANDO POSICIÓN INMEDIATAMENTE.")
            self.cerrar_posicion_mercado(plan['side'], qty_final)
            return False, None

        sl_order_id = res_sl['orderId']
        self.log.registrar_actividad("ORDER_MANAGER", f"🛡️ Stop Loss activado @ {sl_price} (ID: {sl_order_id})")

        # 3. COLOCACIÓN DE TAKE PROFITS
        tps_ids = []
        if 'tps' in plan:
            for tp in plan['tps']:
                tp_qty = self._redondear_cantidad(tp['qty'])
                tp_price = self._redondear_precio(tp['price'])
                
                params_tp = {
                    'symbol': self.cfg.SYMBOL,
                    'side': sl_side, 
                    'type': 'LIMIT',
                    'price': tp_price,
                    'quantity': tp_qty,
                    'positionSide': plan['side'],
                    'timeInForce': 'GTC'
                }
                
                res_tp = self.conn.place_order(params_tp)
                if res_tp:
                    tps_ids.append({'id': res_tp['orderId'], 'price': tp_price, 'qty': tp_qty})
                    self.log.registrar_actividad("ORDER_MANAGER", f"💰 TP colocado @ {tp_price} (Qty: {tp_qty})")

        # 4. PAQUETE DE CUSTODIA
        paquete_posicion = {
            'id': pos_id,
            'timestamp': int(time.time() * 1000),
            'strategy': plan['strategy'],
            'side': plan['side'], 
            'entry_price': real_entry_price,
            'qty': qty_final,
            'sl_price': sl_price,
            'sl_order_id': sl_order_id,
            'tps_config': tps_ids, 
            'status': 'OPEN'
        }
        
        self.log.registrar_orden(paquete_posicion)
        return True, paquete_posicion

    def cancelar_orden(self, order_id):
        return self.conn.cancel_order(self.cfg.SYMBOL, order_id)

    def cerrar_posicion_mercado(self, position_side, qty):
        side = 'SELL' if position_side == 'LONG' else 'BUY' 
        params = {
            'symbol': self.cfg.SYMBOL,
            'side': side, 
            'type': 'MARKET',
            'quantity': qty,
            'positionSide': position_side
        }
        self.conn.place_order(params)

    def _redondear_precio(self, precio):
        return round(precio, 2) 

    def _redondear_cantidad(self, qty):
        return round(qty, 3)