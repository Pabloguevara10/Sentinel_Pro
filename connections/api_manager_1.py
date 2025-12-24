import time
from binance.um_futures import UMFutures
from binance.error import ClientError
from config.config_1 import Config

class APIManager:
    """
    DEPARTAMENTO DE COMUNICACIONES (V15.1 - ROBUST FIX):
    - Soluciona el error 'list index out of range'.
    - Manejo seguro de listas vacías en get_position_info.
    - Soporte completo para Hedge Mode y Stop Loss manual.
    """
    def __init__(self, logger):
        self.log = logger
        self.client = None
        self._conectar_y_validar()

    def _conectar_y_validar(self):
        try:
            if Config.TESTNET:
                base_url = 'https://testnet.binancefuture.com'
                self.log.registrar_actividad("API_MANAGER", "📡 Conectando con Binance Futures (TESTNET)...")
            else:
                base_url = 'https://fapi.binance.com'
                self.log.registrar_actividad("API_MANAGER", "📡 Conectando con Binance Futures (REAL)...")

            self.client = UMFutures(
                key=Config.API_KEY, 
                secret=Config.API_SECRET,
                base_url=base_url
            )
            
            # Sincronización de Tiempo
            try:
                server_time = self.client.time()['serverTime']
                diff = int(time.time() * 1000) - server_time
                if abs(diff) > 1000:
                    self.log.registrar_actividad("API_MANAGER", f"⚠️ Ajuste de reloj: {diff}ms")
            except Exception:
                pass # No detener arranque por fallo de reloj no crítico

            self._configurar_cuenta()
            self.log.registrar_actividad("API_MANAGER", "✅ Conexión Establecida y Cuenta Validada.")

        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Fallo crítico de conexión: {e}", critico=True)
            raise e

    def _configurar_cuenta(self):
        try:
            # 1. Modo Hedge
            try:
                self.client.change_position_mode(dualSidePosition='true')
            except ClientError as e:
                if -4059 != e.error_code: raise e

            # 2. Modo Margen
            try:
                self.client.change_margin_type(symbol=Config.SYMBOL, marginType=Config.MARGIN_TYPE)
            except ClientError as e:
                if 'No need to change' not in str(e): raise e

            # 3. Apalancamiento
            try:
                self.client.change_leverage(symbol=Config.SYMBOL, leverage=Config.LEVERAGE)
            except Exception: pass
            
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error configurando cuenta: {e}", critico=True)

    # --- CONSULTA DE DATOS ---

    def get_ticker_price(self, symbol):
        try:
            return float(self.client.ticker_price(symbol=symbol)['price'])
        except Exception:
            return 0.0

    def get_position_info(self, symbol):
        """
        Retorna la posición activa de forma SEGURA.
        SOLUCIÓN AL ERROR 'list index out of range'.
        """
        try:
            # Solicitamos riesgo de posición
            positions = self.client.get_position_risk(symbol=symbol)
            
            # 1. Validación: ¿Es una lista válida?
            if not positions or not isinstance(positions, list):
                return None # Retorno seguro si Binance falla
            
            # 2. Búsqueda: ¿Hay alguna con tamaño != 0?
            for p in positions:
                if float(p.get('positionAmt', 0)) != 0:
                    return p 
            
            # 3. Fallback: Si no hay activas, devolver la primera (LONG) si existe
            if len(positions) > 0:
                return positions[0]
            
            # 4. Si la lista está vacía (len == 0), retornar None
            return None
            
        except Exception as e:
            # Loguear error pero no detener el flujo con un crash
            self.log.registrar_error("API_MANAGER", f"Error obteniendo info posición: {e}")
            return None

    def get_historical_candles(self, symbol, interval, limit=1000, start_time=None):
        try:
            params = {'symbol': symbol, 'interval': interval, 'limit': limit}
            if start_time: params['startTime'] = start_time
            return self.client.klines(**params)
        except Exception: return []

    # --- EJECUCIÓN DE ÓRDENES ---
    
    def place_order(self, params):
        try:
            return self.client.new_order(**params)
        except ClientError as e:
            self.log.registrar_error("API_MANAGER", f"Binance rechazó orden: {e.error_message}")
            return None
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error de ejecución: {e}")
            return None

    def place_market_order(self, symbol, side, qty, position_side=None, reduce_only=False):
        """
        Método helper para órdenes a mercado.
        Soporta 'positionSide' obligatorio para Hedge Mode.
        """
        try:
            params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': float(qty)
            }
            
            if position_side:
                params['positionSide'] = position_side
                
            if reduce_only:
                params['reduceOnly'] = 'true'
                
            return self.place_order(params)
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error armando market order: {e}")
            return None
    
    def cancel_all_open_orders(self, symbol):
        try:
            self.client.cancel_open_orders(symbol=symbol)
            return True
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error cancelando órdenes: {e}")
            return False

    def cancel_order(self, symbol, order_id):
        try:
            self.client.cancel_order(symbol=symbol, orderId=order_id)
            return True
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error cancelando orden {order_id}: {e}")
            return False