<<<<<<< HEAD
import time
from binance.exceptions import BinanceAPIException

class OrderManager:
    """
    ORDER MANAGER HÍBRIDO (V15.0 - HEDGE PROTOCOL FINAL):
    - Gestión completa de Órdenes en Modo Hedge.
    - Corrección CRÍTICA en Stop Loss: Usa 'closePosition=true' sin cantidad.
    - Protocolo de Insistencia para asegurar protección.
=======
# =============================================================================
# UBICACIÓN: execution/order_manager.py
# DESCRIPCIÓN: ORDER MANAGER V16.0 (HYBRID: V15 LOGIC + V8 BLINDING)
# =============================================================================

import time
import math
from datetime import datetime
from binance.error import ClientError

class OrderManager:
    """
    ORDER MANAGER V16.0 (DEFINITIVO):
    - Base Lógica: V15.14 (Polling robusto y manejo de estados).
    - Blindaje: Calibración automática de precisión con Binance.
    - Seguridad: Sanitización matemática de entradas.
>>>>>>> 4c4d97b (commit 24/12)
    """
    def __init__(self, config, api_manager, logger):
        self.cfg = config
        self.api = api_manager
        self.log = logger
<<<<<<< HEAD

    def ejecutar_estrategia(self, plan):
        """
        Ejecuta la entrada al mercado e INMEDIATAMENTE intenta blindarla con SL.
        """
        symbol = plan['symbol']
        side = plan['side']
        qty = plan['qty']
        
        self.log.registrar_actividad("ORDER_MGR", f"⚡ Ejecutando: {side} {symbol} x{qty}")

        # 1. EJECUTAR ENTRADA (MARKET)
        # En Hedge Mode, 'positionSide' es obligatorio.
        order = self.api.place_market_order(symbol, 'BUY' if side=='LONG' else 'SELL', qty, position_side=side)
        
        if not order:
            self.log.registrar_error("ORDER_MGR", "Fallo al colocar orden de mercado.")
            return False, None

        # Recuperación de precio promedio real
        avg_price = float(order.get('avgPrice', 0.0))
        if avg_price == 0.0:
            cumm = float(order.get('cumQuote', 0.0))
            exec_qty = float(order.get('executedQty', 0.0))
            if exec_qty > 0: 
                avg_price = cumm / exec_qty
            else: 
                # Último recurso: precio del ticker
                avg_price = self.api.get_ticker_price(symbol)
                if avg_price == 0: avg_price = plan['entry_price']

        plan['entry_price'] = avg_price
        plan['order_id'] = order['orderId']
        plan['timestamp'] = time.time()
        
        self.log.registrar_actividad("ORDER_MGR", f"✅ Entrada confirmada @ {avg_price:.2f}")

        # 2. PROTOCOLO DE PROTECCIÓN (SL)
        # Intentamos colocar el SL inmediatamente
        sl_price = plan['sl_price']
        
        if self._colocar_sl_con_insistencia(symbol, side, sl_price):
            self.log.registrar_actividad("ORDER_MGR", f"🛡️ SL Inicial asegurado en {sl_price}")
            return True, plan
        else:
            # Si falla la protección tras varios intentos, CERRAMOS por seguridad.
            self.log.registrar_error("ORDER_MGR", "🚨 EMERGENCIA: SL falló tras reintentos. CERRANDO POSICIÓN.")
            self.cerrar_posicion(symbol, "EMERGENCY_SL_FAIL")
            return False, None

    def actualizar_stop_loss(self, symbol, new_sl_price):
        """
        Actualiza el SL colocando uno nuevo primero y borrando los viejos después.
        """
        # Verificar que existe posición
        pos = self.api.get_position_info(symbol)
        if not pos or float(pos['positionAmt']) == 0: return False
        
        amt = float(pos['positionAmt'])
        side = 'LONG' if amt > 0 else 'SHORT'
        
        # 1. Poner Nuevo SL
        if self._colocar_stop_loss_orden(symbol, side, new_sl_price):
            # 2. Borrar Viejos (Limpieza)
            try:
                ops = self.api.client.get_open_orders(symbol=symbol)
                for o in ops:
                    if o['type'] == 'STOP_MARKET':
                        stop_p = float(o.get('stopPrice', 0))
                        # Borramos solo si el precio es distinto al que acabamos de poner
                        if abs(stop_p - new_sl_price) > 0.01:
                            self.api.cancel_order(symbol, o['orderId'])
            except: 
                pass # Si falla borrar el viejo, no es crítico, mejor tener 2 SL que ninguno
=======
        
        # 1. Variables de Precisión (Default seguro)
        self.qty_precision = 3     
        self.price_precision = 2   
        self.min_qty = 0.1         
        
        # 2. CALIBRACIÓN AL INICIO (NUEVO DEL BLINDAJE)
        self._calibrar_precision_con_exchange()

    def _calibrar_precision_con_exchange(self):
        """Consulta a Binance los decimales exactos permitidos."""
        try:
            # Intentamos obtener info del exchange
            info = self.api.client.exchange_info()
            found = False
            for symbol_data in info['symbols']:
                if symbol_data['symbol'] == self.cfg.SYMBOL:
                    found = True
                    for f in symbol_data['filters']:
                        # Filtro de Cantidad (LOT_SIZE)
                        if f['filterType'] == 'LOT_SIZE':
                            step_size = float(f['stepSize'])
                            self.min_qty = float(f['minQty'])
                            self.qty_precision = int(round(-math.log(step_size, 10), 0))
                        
                        # Filtro de Precio (PRICE_FILTER)
                        if f['filterType'] == 'PRICE_FILTER':
                            tick_size = float(f['tickSize'])
                            self.price_precision = int(round(-math.log(tick_size, 10), 0))
                    
                    self.log.registrar_actividad("ORDER_MGR", 
                        f"🛡️ Calibrado: Qty={self.qty_precision} dec, Price={self.price_precision} dec")
                    break
            
            if not found:
                self.log.registrar_error("ORDER_MGR", f"⚠️ Símbolo {self.cfg.SYMBOL} no encontrado en API.")
                
        except Exception as e:
            self.log.registrar_error("ORDER_MGR", f"Fallo en calibración (Usando defaults): {e}")

    def _blindar_float(self, value, precision):
        """Corta decimales sin redondear hacia arriba (evita error de saldo)."""
        try:
            factor = 10 ** precision
            return math.floor(value * factor) / factor
        except: return value

    # ==============================================================================
    # EJECUCIÓN DE ESTRATEGIA (LÓGICA V15 MEJORADA)
    # ==============================================================================
    def ejecutar_estrategia(self, plan):
        """
        Ejecuta Entrada -> Espera Llenado (Polling) -> Ejecuta SL.
        """
        try:
            # 1. Preparar Datos
            symbol = self.cfg.SYMBOL
            side = plan['side']
            raw_entry = float(plan['price'])
            
            # --- BLINDAJE MATEMÁTICO (NUEVO) ---
            # Ajustamos la cantidad a los decimales exactos de Binance
            raw_qty = float(plan['qty'])
            qty = self._blindar_float(raw_qty, self.qty_precision)
            
            # Validación de Mínimos
            if qty < self.min_qty:
                self.log.registrar_error("ORDER_MGR", f"⛔ Orden muy pequeña: {qty} < {self.min_qty}")
                return False, None

            self.log.registrar_actividad("ORDER_MGR", f"⚡ Iniciando: {side} {symbol} x{qty}")

            # -----------------------------------------------------------
            # PASO 1: ENTRADA A MERCADO
            # -----------------------------------------------------------
            # Definir Lados para API (Hedge Mode)
            pos_side = side # 'LONG' o 'SHORT'
            order_side = 'BUY' if side == 'LONG' else 'SELL'
            
            # Ejecutar con API Manager
            ok_entry, resp_entry = self.api.place_market_order(
                symbol=symbol,
                side=order_side,
                qty=qty,
                position_side=pos_side
            )

            if not ok_entry:
                self.log.registrar_error("ORDER_MGR", f"❌ Fallo Entrada: {resp_entry}")
                return False, None

            order_id = resp_entry['orderId']
            
            # -----------------------------------------------------------
            # PASO 2: POLLING (ESPERA ACTIVA V15)
            # -----------------------------------------------------------
            # Esperamos a que la orden pase de NEW a FILLED
            fill_price, filled_qty = self._esperar_llenado(symbol, order_id)
            
            if fill_price == 0:
                self.log.registrar_error("ORDER_MGR", "⚠️ Timeout esperando llenado. Cancelando operación.")
                self.cancelar_orden(order_id)
                return False, None

            self.log.registrar_actividad("ORDER_MGR", f"✅ Entrada Confirmada @ {fill_price}")

            # -----------------------------------------------------------
            # PASO 3: STOP LOSS (PROTECCIÓN)
            # -----------------------------------------------------------
            # Calcular SL basado en el plan o blindado
            sl_price_raw = float(plan['sl_price'])
            sl_price = round(sl_price_raw, self.price_precision)
            
            sl_side = 'SELL' if side == 'LONG' else 'BUY'
            
            ok_sl, resp_sl = self.api.place_stop_loss(
                symbol=symbol,
                side=sl_side,
                position_side=pos_side,
                stop_price=sl_price
            )

            sl_id = resp_sl['orderId'] if ok_sl else None
            
            if not ok_sl:
                self.log.registrar_error("ORDER_MGR", f"⚠️ ALERTA: SL Falló ({resp_sl}). Cerrando por seguridad.")
                # Cierre de emergencia si no hay SL
                self.cerrar_posicion(symbol) 
                return False, None

            self.log.registrar_actividad("ORDER_MGR", f"🛡️ SL Colocado @ {sl_price}")

            # -----------------------------------------------------------
            # PASO 4: RETORNO DE PAQUETE
            # -----------------------------------------------------------
            paquete = {
                'id': str(uuid.uuid4())[:8],
                'symbol': symbol,
                'side': side,
                'entry_price': fill_price,
                'qty': filled_qty,
                'sl_price': sl_price,
                'sl_order_id': sl_id,
                'timestamp': time.time(),
                'status': 'OPEN'
            }
            
            self._registrar_en_csv(paquete)
            return True, paquete

        except Exception as e:
            self.log.registrar_error("ORDER_MGR", f"Excepción Crítica: {e}")
            return False, None

    def _esperar_llenado(self, symbol, order_id, retries=10):
        """Espera activa (Polling) para confirmar precio real de entrada."""
        for i in range(retries):
            try:
                # Usamos client directo para mayor velocidad
                order = self.api.client.query_order(symbol=symbol, orderId=order_id)
                status = order['status']
                
                if status == 'FILLED':
                    avg_price = float(order['avgPrice'])
                    qty = float(order['executedQty'])
                    return avg_price, qty
                
                elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    return 0, 0
                
                time.sleep(0.5) # Espera 500ms
                
            except Exception as e:
                self.log.registrar_error("ORDER_MGR", f"Polling error: {e}")
                time.sleep(0.5)
        
        return 0, 0

    # ==============================================================================
    # MÉTODOS DE GESTIÓN (COMPATIBILIDAD V15)
    # ==============================================================================
    def cancelar_orden(self, order_id):
        """Cancela una orden por ID."""
        return self.api.cancel_order(self.cfg.SYMBOL, order_id)

    def cancelar_todo(self):
        """Cancela todas las órdenes abiertas."""
        return self.api.cancel_all_orders()

    def cerrar_posicion(self, symbol, reason="EXIT"):
        """Cierra la posición completa a mercado."""
        try:
            self.api.cancel_all_open_orders(symbol)
            pos = self.api.get_position_info(symbol)
            
            # Buscar posición activa
            target_pos = None
            if isinstance(pos, list):
                for p in pos:
                    if float(p['positionAmt']) != 0:
                        target_pos = p
                        break
            else:
                target_pos = pos if float(pos['positionAmt']) != 0 else None

            if not target_pos: return True # Ya estaba cerrada

            qty = abs(float(target_pos['positionAmt']))
            side = 'LONG' if float(target_pos['positionAmt']) > 0 else 'SHORT'
            
            # Operación contraria
            close_side = 'SELL' if side == 'LONG' else 'BUY'
            
            self.api.place_market_order(
                symbol=symbol, 
                side=close_side, 
                qty=qty, 
                position_side=side
            )
>>>>>>> 4c4d97b (commit 24/12)
            return True
        except: return False
        
    def reducir_posicion(self, symbol, qty, reason="PARTIAL"):
        """Cierre parcial blindado."""
        try:
            # Blindar cantidad
            final_qty = self._blindar_float(qty, self.qty_precision)
            
            # Obtener lado actual (asumiendo que lo sabemos o lo consultamos)
            # Simplificado para no hacer otra call a la API si no es necesario
            # Pero para seguridad consultamos:
            pos = self.api.get_position_info(symbol)
            target_pos = None
            for p in pos:
                if float(p['positionAmt']) != 0:
                    target_pos = p; break
            
            if not target_pos: return False
            
            side = 'LONG' if float(target_pos['positionAmt']) > 0 else 'SHORT'
            close_side = 'SELL' if side == 'LONG' else 'BUY'

<<<<<<< HEAD
    def _colocar_sl_con_insistencia(self, symbol, side, sl_price):
        """
        Intenta colocar el SL hasta 4 veces.
        Verifica que el precio no haya cruzado el SL antes de intentar.
        """
        for i in range(4): 
            curr = self.api.get_ticker_price(symbol)
            
            # Abortar si el precio ya tocó el SL (ya es tarde)
            if (side=='LONG' and curr<=sl_price) or (side=='SHORT' and curr>=sl_price): 
                return False
            
            if self._colocar_stop_loss_orden(symbol, side, sl_price): 
                return True
            
            time.sleep(0.5) # Pausa breve entre intentos
        return False

    def _colocar_stop_loss_orden(self, symbol, side_posicion, sl_price):
        """
        MÉTODO CRÍTICO PARA HEDGE MODE:
        Usa 'closePosition=true' para cerrar la posición entera.
        IMPORTANTE: NO enviar 'quantity' aquí.
        """
        try:
            side_order = 'SELL' if side_posicion == 'LONG' else 'BUY'
            prec = getattr(self.cfg, 'PRICE_PRECISION', 2)
            price_str = "{:0.{}f}".format(sl_price, prec)

            params = {
                'symbol': symbol,
                'side': side_order,
                'type': 'STOP_MARKET',
                'stopPrice': price_str,
                'closePosition': 'true',  # Esto le dice a Binance: "Cierra todo lo que tenga en este lado"
                'positionSide': side_posicion
            }
            
            # Enviamos la orden
            return self.api.place_order(params) is not None
            
        except Exception as e:
            self.log.registrar_error("ORDER_MGR", f"Error SL API: {e}")
            return False

    def reducir_posicion(self, symbol, qty, reason="PARTIAL"):
        """
        Cierra una parte de la posición (Take Profit Parcial).
        """
        try:
            pos = self.api.get_position_info(symbol)
            if not pos or float(pos['positionAmt'])==0: return False
            
            amt = float(pos['positionAmt'])
            side = 'LONG' if amt > 0 else 'SHORT'
            
            # Para reducir, operamos en contra: Long -> Sell, Short -> Buy
            side_close = 'SELL' if side == 'LONG' else 'BUY'
            
            self.api.place_market_order(symbol, side_close, qty, position_side=side)
            return True
        except: return False

    def cerrar_posicion(self, symbol, reason="EXIT"):
        """
        Cierra la posición completa y cancela todas las órdenes pendientes.
        """
        try:
            # 1. Limpiar SLs pendientes
            self.api.cancel_all_open_orders(symbol)
            
            # 2. Cerrar posición de mercado
            pos = self.api.get_position_info(symbol)
            if not pos or float(pos['positionAmt'])==0: return True
            
            qty = abs(float(pos['positionAmt']))
            side = 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT'
            side_close = 'SELL' if side == 'LONG' else 'BUY'
            
            self.api.place_market_order(symbol, side_close, qty, position_side=side)
            return True
        except: return False
=======
            self.api.place_market_order(
                symbol=symbol,
                side=close_side,
                qty=final_qty,
                position_side=side,
                reduce_only=True
            )
            return True
        except: return False

    def _registrar_en_csv(self, paquete):
        try:
            ts_str = datetime.fromtimestamp(paquete['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
            line = f"{paquete['id']},{ts_str},SNIPER,{paquete['side']},{paquete['entry_price']},{paquete['qty']},{paquete['sl_price']},{paquete['sl_order_id']},NONE,OPEN\n"
            with open(self.cfg.FILE_ORDERS, 'a') as f: f.write(line)
        except: pass
>>>>>>> 4c4d97b (commit 24/12)
