import time
from binance.um_futures import UMFutures
from binance.error import ClientError
from config.config import Config

class APIManager:
    """
    DEPARTAMENTO DE COMUNICACIONES (V11.4):
    Incluye 'get_open_positions_info' para auditoría de realidad.
    """
    def __init__(self, logger):
        self.log = logger
        self.client = None
        self._conectar_y_validar()

    def _conectar_y_validar(self):
        try:
            self.client = UMFutures(
                key=Config.API_KEY, 
                secret=Config.API_SECRET,
                base_url='https://testnet.binancefuture.com'
            )
            
            self.log.registrar_actividad("API_MANAGER", "📡 Conectando con Binance Futures (TESTNET)...")
            
            server_time = self.client.time()['serverTime']
            diff = int(time.time() * 1000) - server_time
            if abs(diff) > 1000:
                self.log.registrar_actividad("API_MANAGER", f"⚠️ Ajuste de tiempo: {diff}ms")

            self._configurar_cuenta()
            self.log.registrar_actividad("API_MANAGER", "✅ Conexión Establecida y Cuenta Validada (HEDGE/ISOLATED).")

        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Fallo crítico de conexión: {e}", critico=True)
            raise e

    def _configurar_cuenta(self):
        try:
            try:
                self.client.change_position_mode(dualSidePosition='true')
            except ClientError as e:
                if -4059 != e.error_code: raise e

            try:
                self.client.change_margin_type(symbol=Config.SYMBOL, marginType=Config.MARGIN_TYPE)
            except ClientError as e:
                if 'No need to change' not in str(e): raise e

            self.client.change_leverage(symbol=Config.SYMBOL, leverage=Config.LEVERAGE)
            
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error configurando cuenta: {e}", critico=True)
            raise e

    # --- DATOS ---

    def get_ticker_price(self, symbol):
        try:
            return float(self.client.ticker_price(symbol=symbol)['price'])
        except Exception:
            return 0.0

    def get_open_positions_info(self):
        """
        NUEVO: Descarga las posiciones reales desde Binance para auditoría.
        """
        try:
            return self.client.get_position_risk(symbol=Config.SYMBOL)
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error obteniendo posiciones: {e}")
            return []

    def get_historical_candles(self, symbol, interval, limit=1000, start_time=None):
        try:
            params = {'symbol': symbol, 'interval': interval, 'limit': limit}
            if start_time: params['startTime'] = start_time
            return self.client.klines(**params)
        except Exception: return []

    # --- EJECUCIÓN ---
    
    def place_order(self, params):
        try:
            return self.client.new_order(**params)
        except ClientError as e:
            self.log.registrar_error("API_MANAGER", f"Binance rechazó orden: {e.error_message}")
            return None
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error de ejecución: {e}")
            return None
    
    def cancel_order(self, symbol, order_id):
        try:
            self.client.cancel_order(symbol=symbol, orderId=order_id)
            return True
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error cancelando orden {order_id}: {e}")
            return False

    def cancel_all_orders(self, symbol):
        try:
            self.client.cancel_open_orders(symbol=symbol)
        except Exception: pass