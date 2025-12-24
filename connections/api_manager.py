import time
from binance.um_futures import UMFutures
from binance.error import ClientError
from config.config import Config

class APIManager:
    """
<<<<<<< HEAD
    DEPARTAMENTO DE COMUNICACIONES (V15.1 - ROBUST FIX):
    - Soluciona el error 'list index out of range'.
    - Manejo seguro de listas vacías en get_position_info.
    - Soporte completo para Hedge Mode y Stop Loss manual.
=======
    DEPARTAMENTO DE COMUNICACIONES (V7.8 - COMPATIBLE & DUAL):
    - Estructura idéntica al V15 (Importa Config internamente).
    - Soporte Dual Testnet/Live sin cambiar el constructor.
>>>>>>> 4c4d97b (commit 24/12)
    """
    def __init__(self, logger):
        self.log = logger
        self.client = None
        self._conectar_y_validar()

    def _conectar_y_validar(self):
        try:
<<<<<<< HEAD
            if Config.TESTNET:
=======
            # Lógica Dual usando la Config importada
            if Config.MODE == 'TESTNET':
>>>>>>> 4c4d97b (commit 24/12)
                base_url = 'https://testnet.binancefuture.com'
                self._log_msg("📡 Conectando con Binance Futures (TESTNET)...")
            else:
                base_url = 'https://fapi.binance.com'
<<<<<<< HEAD
                self.log.registrar_actividad("API_MANAGER", "📡 Conectando con Binance Futures (REAL)...")
=======
                self._log_msg("🚨 Conectando con Binance Futures (REAL)...")

            # Validar credenciales
            if not Config.API_KEY or not Config.API_SECRET:
                raise ValueError(f"Credenciales vacías para modo {Config.MODE}")
>>>>>>> 4c4d97b (commit 24/12)

            self.client = UMFutures(
                key=Config.API_KEY, 
                secret=Config.API_SECRET,
                base_url=base_url
            )
            
<<<<<<< HEAD
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
=======
            # Prueba de vida
            server_time = self.client.time()['serverTime']
            self._log_msg(f"Conexión Establecida. Ping: {server_time}")
            
        except Exception as e:
            self._log_err(f"Error crítico de conexión: {e}")
            raise e
>>>>>>> 4c4d97b (commit 24/12)

    # Helpers de log compatibles
    def _log_msg(self, msg):
        if hasattr(self.log, 'registrar_actividad'): self.log.registrar_actividad("API_MANAGER", msg)
        elif hasattr(self.log, 'log_operational'): self.log.log_operational("API_MANAGER", msg)
        else: print(f"[API] {msg}")

    def _log_err(self, msg):
        if hasattr(self.log, 'registrar_error'): self.log.registrar_error("API_MANAGER", msg)
        elif hasattr(self.log, 'log_error'): self.log.log_error("API_MANAGER", msg)
        else: print(f"[API ERROR] {msg}")

<<<<<<< HEAD
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
=======
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
>>>>>>> 4c4d97b (commit 24/12)
            return None

    def get_historical_candles(self, symbol, interval, limit=100, start_time=None):
        try:
            params = {'symbol': symbol, 'interval': interval, 'limit': limit}
            if start_time: params['startTime'] = start_time
            return self.client.klines(**params)
        except Exception as e:
<<<<<<< HEAD
            self.log.registrar_error("API_MANAGER", f"Error de ejecución: {e}")
            return None

    def place_market_order(self, symbol, side, qty, position_side=None, reduce_only=False):
        """
        Método helper para órdenes a mercado.
        Soporta 'positionSide' obligatorio para Hedge Mode.
        """
=======
            self._log_err(f"Fallo klines: {e}")
            return []

    # --- MÉTODOS DE EJECUCIÓN (FIRMA V15) ---

    def place_market_order(self, symbol, side, qty, position_side=None, reduce_only=False):
>>>>>>> 4c4d97b (commit 24/12)
        try:
            params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': float(qty)
            }
<<<<<<< HEAD
            
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
=======
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
>>>>>>> 4c4d97b (commit 24/12)

    def cancel_order(self, symbol, order_id):
        try:
            self.client.cancel_order(symbol=symbol, orderId=order_id)
            return True
        except Exception as e:
<<<<<<< HEAD
            self.log.registrar_error("API_MANAGER", f"Error cancelando orden {order_id}: {e}")
            return False
=======
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
>>>>>>> 4c4d97b (commit 24/12)
