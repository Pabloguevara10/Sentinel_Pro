import uuid
import time
from binance.error import ClientError

class OrderManager:
    """
    DEPARTAMENTO DE OPERACIONES (Ejecución V12.0 - REFINADO):
    - Ejecuta órdenes de entrada con polling robusto.
    - Coloca protecciones iniciales (SL y Hard TP).
    - Gestiona actualizaciones seguras de SL (Protocolo Overlap).
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

        # Usamos el conector directo para place_order
        res_entry = self.conn.place_order(params_entry)
        
        if not res_entry or 'orderId' not in res_entry:
            self.log.registrar_error("ORDER_MANAGER", f"Fallo en Entrada: {res_entry}")
            return False, None

        entry_order_id = res_entry['orderId']
        pos_id = str(uuid.uuid4())[:8]

        # 2. BUCLE DE CONFIRMACIÓN INSISTENTE (Wait for FILL)
        filled = False
        intentos = 0
        max_intentos = 5 # Esperar hasta 2.5 segundos
        real_entry_price = 0.0
        
        while intentos < max_intentos:
            try:
                # Polling directo al cliente de binance
                order_status = self.conn.client.query_order(symbol=self.cfg.SYMBOL, orderId=entry_order_id)
                status = order_status.get('status', 'UNKNOWN')
                
                if status in ['FILLED', 'PARTIALLY_FILLED']:
                    filled = True
                    real_entry_price = float(order_status.get('avgPrice', 0.0))
                    if real_entry_price == 0: 
                        real_entry_price = self.conn.get_ticker_price(self.cfg.SYMBOL)
                    break
                
            except Exception as e:
                self.log.registrar_error("ORDER_MANAGER", f"Polling leve orden {entry_order_id}: {e}")
            
            time.sleep(0.5)
            intentos += 1
        
        if not filled:
            self.log.registrar_actividad("ORDER_MANAGER", "⚠️ Orden enviada pero no confirmada FILLED a tiempo. Asumiendo ejecución.")
            real_entry_price = self.conn.get_ticker_price(self.cfg.SYMBOL)

        self.log.registrar_actividad("ORDER_MANAGER", f"✅ Entrada Confirmada (ID: {entry_order_id}). Precio Base: {real_entry_price}")

        # 3. COLOCACIÓN DE PROTECCIONES (SL y HARD TP)
        
        # A. STOP LOSS
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

        # B. HARD TAKE PROFIT (Si aplica)
        tp_hard_price = plan.get('tp_hard_price', 0.0)
        tp_hard_id = None
        
        if tp_hard_price > 0:
            tp_price = self._redondear_precio(tp_hard_price)
            params_tp = {
                'symbol': self.cfg.SYMBOL,
                'side': api_side_exit,
                'type': 'TAKE_PROFIT_MARKET',
                'stopPrice': tp_price,
                'positionSide': plan['side'],
                'timeInForce': 'GTC',
                'closePosition': 'true'
            }
            res_tp = self.conn.place_order(params_tp)
            if res_tp and 'orderId' in res_tp:
                tp_hard_id = res_tp['orderId']
                self.log.registrar_actividad("ORDER_MANAGER", f"🚀 Hard TP activado @ {tp_price}")

        # C. TPs Parciales (Sniper Legacy)
        tps_ids = []
        if 'tps' in plan and plan['tps']:
            for tp in plan['tps']:
                tp_qty = self._redondear_cantidad(tp['qty'])
                tp_price = self._redondear_precio(tp['price'])
                
                params_tp_limit = {
                    'symbol': self.cfg.SYMBOL,
                    'side': api_side_exit, 
                    'type': 'LIMIT',
                    'price': tp_price,
                    'quantity': tp_qty,
                    'positionSide': plan['side'],
                    'timeInForce': 'GTC'
                }
                
                res_tp_l = self.conn.place_order(params_tp_limit)
                if res_tp_l:
                    tps_ids.append({'id': res_tp_l['orderId'], 'price': tp_price, 'qty': tp_qty})
                    self.log.registrar_actividad("ORDER_MANAGER", f"💰 TP Parcial colocado @ {tp_price}")

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
            'tp_hard_price': tp_hard_price, # Nuevo campo
            'tp_hard_order_id': tp_hard_id, # Nuevo campo
            'tps_config': tps_ids, 
            'management_type': plan.get('management_type', 'STATIC'), # Para Contralor
            'status': 'OPEN'
        }
        
        self.log.registrar_orden(paquete_posicion)
        return True, paquete_posicion

    def actualizar_stop_loss_seguro(self, symbol, side_posicion, qty, nuevo_precio, id_orden_antigua):
        """
        PROTOCOLO DE SEGURIDAD "OVERLAP" PARA TRAILING STOP:
        1. Coloca el Nuevo SL.
        2. Verifica que Binance confirmó y devolvió un ID válido.
        3. Solo entonces, cancela el SL antiguo.
        """
        try:
            # Determinar el lado de la orden de protección (Inverso a la posición)
            side_sl = 'SELL' if side_posicion == 'LONG' else 'BUY'
            precio_final = self._redondear_precio(nuevo_precio)
            
            # PASO 1: Colocar Nuevo SL (Sin tocar el viejo aún)
            # self.log.registrar_actividad("ORDER_MANAGER", f"🛡️ Ajustando Trailing SL a {precio_final}...")
            
            # Construcción manual de params para usar place_order del conector
            params = {
                'symbol': symbol,
                'side': side_sl,
                'type': 'STOP_MARKET',
                'stopPrice': precio_final,
                'positionSide': side_posicion, # Binance Futures Hedge Mode requiere esto
                'closePosition': 'true',
                'timeInForce': 'GTC'
            }
            
            res = self.conn.place_order(params)
            
            nuevo_id = None
            if res and 'orderId' in res:
                nuevo_id = res['orderId']
            
            if not nuevo_id:
                self.log.registrar_error("ORDER_MANAGER", "❌ Binance no confirmó el nuevo SL. Abortando cambio. (SL Viejo mantenido)")
                return False

            # PASO 2: Eliminar Viejo SL (Ya estamos seguros con el nuevo)
            try:
                self.cancelar_orden(id_orden_antigua)
                self.log.registrar_actividad("ORDER_MANAGER", f"✅ SL actualizado a {precio_final}. Protección asegurada.")
            except Exception as e:
                # Advertencia menor: Tenemos 2 SLs activos. Es redundante pero SEGURO.
                self.log.registrar_error("ORDER_MANAGER", f"⚠️ Aviso: No se borró el SL viejo ({id_orden_antigua}). Revisar manual. Error: {e}")

            return True

        except Exception as e:
            self.log.registrar_error("ORDER_MANAGER", f"⛔ Error Desconocido al mover SL: {e}")
            return False

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