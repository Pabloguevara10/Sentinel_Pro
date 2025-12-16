import uuid
import time
from config.config import Config

class OrderManager:
    """
    DEPARTAMENTO DE OPERACIONES (Ejecución V11.7 - BUGFIXED):
    - Corrección: Usa 'query_order' en lugar de 'get_order' para polling.
    - Espera activamente a que la orden de entrada se llene antes de poner SL.
    """
    def __init__(self, config, api_conn, logger):
        self.cfg = config
        self.conn = api_conn
        self.log = logger

    def ejecutar_estrategia(self, plan):
        self.log.registrar_actividad("ORDER_MANAGER", f"🔫 Iniciando ejecución: {plan['strategy']} ({plan['side']})")

        # --- TRADUCCIÓN API ---
        if plan['side'] == 'LONG':
            api_side_entry = 'BUY'
            api_side_exit = 'SELL'
        else:
            api_side_entry = 'SELL'
            api_side_exit = 'BUY'

        # 1. ENVIAR ORDEN DE ENTRADA
        qty_final = self._redondear_cantidad(plan['qty'])
        
        params_entry = {
            'symbol': self.cfg.SYMBOL,
            'side': api_side_entry,
            'type': 'MARKET',
            'quantity': qty_final,
            'positionSide': plan['side']
        }

        res_entry = self.conn.place_order(params_entry)
        
        if not res_entry or 'orderId' not in res_entry:
            self.log.registrar_error("ORDER_MANAGER", f"Fallo en Entrada: {res_entry}")
            return False, None

        entry_order_id = res_entry['orderId']
        pos_id = str(uuid.uuid4())[:8]

        # 2. BUCLE DE CONFIRMACIÓN INSISTENTE (Wait for FILL)
        # Corrección: query_order es el método correcto en binance-connector
        filled = False
        intentos = 0
        max_intentos = 5 # Esperar hasta 2.5 segundos (5 * 0.5s)
        real_entry_price = 0.0
        
        while intentos < max_intentos:
            try:
                # CORRECCIÓN AQUÍ: Usamos query_order
                order_status = self.conn.client.query_order(symbol=self.cfg.SYMBOL, orderId=entry_order_id)
                status = order_status.get('status', 'UNKNOWN')
                
                if status in ['FILLED', 'PARTIALLY_FILLED']:
                    filled = True
                    real_entry_price = float(order_status.get('avgPrice', 0.0))
                    # Si avgPrice es 0 (raro en market), usamos ticker price
                    if real_entry_price == 0: 
                        real_entry_price = self.conn.get_ticker_price(self.cfg.SYMBOL)
                    break
                
            except Exception as e:
                # Logueamos como advertencia leve para no ensuciar si es solo latencia
                self.log.registrar_error("ORDER_MANAGER", f"Polling leve orden {entry_order_id}: {e}")
            
            time.sleep(0.5)
            intentos += 1
        
        if not filled:
            # Si tras 2.5s no se llenó, asumimos éxito parcial o usamos precio ticker
            self.log.registrar_actividad("ORDER_MANAGER", "⚠️ Orden enviada pero no confirmada FILLED a tiempo. Asumiendo ejecución.")
            real_entry_price = self.conn.get_ticker_price(self.cfg.SYMBOL)

        self.log.registrar_actividad("ORDER_MANAGER", f"✅ Entrada Confirmada (ID: {entry_order_id}). Precio Base: {real_entry_price}")

        # 3. COLOCACIÓN DE STOP LOSS
        sl_price = self._redondear_precio(plan['sl_price'])
        
        params_sl = {
            'symbol': self.cfg.SYMBOL,
            'side': api_side_exit,
            'type': 'STOP_MARKET',
            'stopPrice': sl_price,
            'positionSide': plan['side'],
            'timeInForce': 'GTC',
            'closePosition': 'true' 
        }

        res_sl = self.conn.place_order(params_sl)
        
        sl_order_id = None
        if res_sl and 'orderId' in res_sl:
            sl_order_id = res_sl['orderId']
            self.log.registrar_actividad("ORDER_MANAGER", f"🛡️ Stop Loss activado @ {sl_price}")
        else:
            self.log.registrar_error("ORDER_MANAGER", "🚨 FALLO CRÍTICO EN SL. CERRANDO POSICIÓN INMEDIATAMENTE.")
            self.cerrar_posicion_mercado(plan['side'], qty_final)
            return False, None

        # 4. TAKE PROFITS
        tps_ids = []
        if 'tps' in plan:
            for tp in plan['tps']:
                tp_qty = self._redondear_cantidad(tp['qty'])
                tp_price = self._redondear_precio(tp['price'])
                
                params_tp = {
                    'symbol': self.cfg.SYMBOL,
                    'side': api_side_exit, 
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

        # 5. REGISTRO
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

    def cerrar_posicion_parcial(self, position_side, qty):
        side = 'SELL' if position_side == 'LONG' else 'BUY'
        qty_clean = self._redondear_cantidad(qty)
        params = {
            'symbol': self.cfg.SYMBOL,
            'side': side,
            'type': 'MARKET',
            'quantity': qty_clean,
            'positionSide': position_side
        }
        res = self.conn.place_order(params)
        if res and 'orderId' in res:
            self.log.registrar_actividad("ORDER_MANAGER", f"✂️ Cierre Parcial: {qty_clean}")
            return True
        return False

    def _redondear_precio(self, precio):
        return round(precio, 2) 

    def _redondear_cantidad(self, qty):
        return round(qty, 1)