import time
from binance.um_futures import UMFutures
from binance.error import ClientError
from config.config import Config

class APIManager:
    """
    DEPARTAMENTO DE COMUNICACIONES (V7.8 - COMPATIBLE & DUAL):
    - Estructura idéntica al V15 (Importa Config internamente).
    - Soporte Dual Testnet/Live sin cambiar el constructor.
    """
    def __init__(self, logger):
        self.log = logger
        self.client = None
        self._conectar_y_validar()

    def _conectar_y_validar(self):
        try:
            # Lógica Dual usando la Config importada
            if Config.MODE == 'TESTNET':
                base_url = 'https://testnet.binancefuture.com'
                self._log_msg("📡 Conectando con Binance Futures (TESTNET)...")
            else:
                base_url = 'https://fapi.binance.com'
                self._log_msg("🚨 Conectando con Binance Futures (REAL)...")

            # Validar credenciales
            if not Config.API_KEY or not Config.API_SECRET:
                raise ValueError(f"Credenciales vacías para modo {Config.MODE}")

            self.client = UMFutures(
                key=Config.API_KEY, 
                secret=Config.API_SECRET,
                base_url=base_url
            )
            
            # Prueba de vida
            server_time = self.client.time()['serverTime']
            self._log_msg(f"Conexión Establecida. Ping: {server_time}")
            
        except Exception as e:
            self._log_err(f"Error crítico de conexión: {e}")
            raise e

    # Helpers de log compatibles
    def _log_msg(self, msg):
        if hasattr(self.log, 'registrar_actividad'): self.log.registrar_actividad("API_MANAGER", msg)
        elif hasattr(self.log, 'log_operational'): self.log.log_operational("API_MANAGER", msg)
        else: print(f"[API] {msg}")

    def _log_err(self, msg):
        if hasattr(self.log, 'registrar_error'): self.log.registrar_error("API_MANAGER", msg)
        elif hasattr(self.log, 'log_error'): self.log.log_error("API_MANAGER", msg)
        else: print(f"[API ERROR] {msg}")

    # --- MÉTODOS DE CONSULTA (LEGACY V15) ---

    def check_heartbeat(self):
        try:
            self.client.time()
            return True
        except: return False

    def get_real_price(self, symbol=None):
        sym = symbol if symbol else Config.SYMBOL
        try:
            ticker = self.client.ticker_price(symbol=sym)
            return float(ticker['price'])
        except Exception as e:
            self._log_err(f"Fallo ticker: {e}")
            return None

    def get_historical_candles(self, symbol, interval, limit=100, start_time=None):
        try:
            params = {'symbol': symbol, 'interval': interval, 'limit': limit}
            if start_time: params['startTime'] = start_time
            return self.client.klines(**params)
        except Exception as e:
            self._log_err(f"Fallo klines: {e}")
            return []

    # --- MÉTODOS DE EJECUCIÓN (FIRMA V15) ---

    def place_market_order(self, symbol, side, qty, position_side=None, reduce_only=False):
        try:
            params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': float(qty)
            }
            if position_side: params['positionSide'] = position_side
            if reduce_only: params['reduceOnly'] = 'true'
            
            return True, self.client.new_order(**params)
        except Exception as e:
            self._log_err(f"Error orden mercado: {e}")
            return False, str(e)

    def place_stop_loss(self, symbol, side, position_side, stop_price):
        try:
            params = {
                'symbol': symbol,
                'side': side,
                'positionSide': position_side,
                'type': 'STOP_MARKET',
                'stopPrice': float(stop_price),
                'closePosition': 'true',
                'timeInForce': 'GTC'
            }
            return True, self.client.new_order(**params)
        except Exception as e:
            return False, str(e)

    # --- GESTIÓN DE ÓRDENES ---

    def cancel_order(self, symbol, order_id):
        try:
            self.client.cancel_order(symbol=symbol, orderId=order_id)
            return True
        except Exception as e:
            self._log_err(f"Error cancelando {order_id}: {e}")
            return False

    def cancel_all_open_orders(self, symbol):
        try:
            self.client.cancel_open_orders(symbol=symbol)
            return True
        except Exception as e:
            self._log_err(f"Error cancelando todo: {e}")
            return False
            
    def cancel_all_orders(self): # Alias
        return self.cancel_all_open_orders(Config.SYMBOL)

    def get_position_info(self, symbol):
        try:
            positions = self.client.get_position_risk(symbol=symbol)
            if not positions: return []
            return positions
        except Exception as e:
            self._log_err(f"Error leyendo posiciones: {e}")
            return []
            
    def get_account_balance(self):
        try:
            assets = self.client.balance()
            for asset in assets:
                if asset['asset'] == 'USDT':
                    return float(asset['balance'])
            return 0.0
        except: return 0.0