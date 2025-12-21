import time
from binance.exceptions import BinanceAPIException

class OrderManager:
    """
    ORDER MANAGER HÍBRIDO (V15.0 - HEDGE PROTOCOL FINAL):
    - Gestión completa de Órdenes en Modo Hedge.
    - Corrección CRÍTICA en Stop Loss: Usa 'closePosition=true' sin cantidad.
    - Protocolo de Insistencia para asegurar protección.
    """
    def __init__(self, config, api_manager, logger):
        self.cfg = config
        self.api = api_manager
        self.log = logger

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
            return True
        return False

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