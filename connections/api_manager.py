import time
from binance.um_futures import UMFutures
from binance.error import ClientError
from config.config import Config

class APIManager:
    """
    DEPARTAMENTO DE COMUNICACIONES:
    Encargado de la conexión segura con Binance, gestión de pesos y
    configuración forzosa de parámetros de seguridad (Hedge/Isolated).
    MODO: TESTNET (Pruebas)
    """
    def __init__(self, logger):
        self.log = logger
        self.client = None
        self._conectar_y_validar()

    def _conectar_y_validar(self):
        """Establece conexión y fuerza las reglas de seguridad de la cuenta."""
        try:
            # --- CORRECCIÓN PARA TESTNET ---
            # Se agrega base_url apuntando a los servidores de prueba
            self.client = UMFutures(
                key=Config.API_KEY, 
                secret=Config.API_SECRET,
                base_url='https://testnet.binancefuture.com' 
            )
            
            self.log.registrar_actividad("API_MANAGER", "📡 Conectando con Binance Futures (TESTNET)...")
            
            # Sincronizar hora para evitar errores de timestamp
            server_time = self.client.time()['serverTime']
            diff = int(time.time() * 1000) - server_time
            if abs(diff) > 1000:
                self.log.registrar_actividad("API_MANAGER", f"⚠️ Ajuste de tiempo necesario. Diferencia: {diff}ms")

            # --- VALIDACIÓN CRÍTICA DE CUENTA ---
            self._configurar_cuenta()
            self.log.registrar_actividad("API_MANAGER", "✅ Conexión Establecida y Cuenta Validada (HEDGE/ISOLATED).")

        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Fallo crítico de conexión: {e}", critico=True)
            raise e

    def _configurar_cuenta(self):
        """
        Fuerza la cuenta al modo requerido por la estrategia.
        Si la cuenta no está en Hedge Mode o Isolated, la cambia automáticamente.
        """
        try:
            # 1. Configurar Modo Hedge (Dual Side)
            try:
                # dualSidePosition: True = Hedge Mode
                self.client.change_position_mode(dualSidePosition='true')
                self.log.registrar_actividad("API_MANAGER", "🔄 Cuenta configurada a HEDGE MODE.")
            except ClientError as e:
                # Si ya está en Hedge Mode, Binance devuelve error -4059 'No need to change'
                if -4059 != e.error_code: 
                    # Solo lanzamos error si es diferente a "no hace falta cambiar"
                    if 'No need to change' not in str(e): raise e

            # 2. Configurar Margen y Apalancamiento para el Símbolo
            try:
                self.client.change_margin_type(symbol=Config.SYMBOL, marginType=Config.MARGIN_TYPE)
                self.log.registrar_actividad("API_MANAGER", f"🛡️ Margen configurado a {Config.MARGIN_TYPE}.")
            except ClientError as e:
                # Si ya está en Isolated, ignoramos
                if 'No need to change' not in str(e): raise e

            self.client.change_leverage(symbol=Config.SYMBOL, leverage=Config.LEVERAGE)
            
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error configurando cuenta: {e}", critico=True)
            raise e

    # --- MÉTODOS DE DATOS DE MERCADO ---

    def get_ticker_price(self, symbol):
        """Retorna el precio actual (float) de forma segura."""
        try:
            info = self.client.ticker_price(symbol=symbol)
            return float(info['price'])
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error leyendo precio: {e}")
            return 0.0

    def get_historical_candles(self, symbol, interval, limit=1000, start_time=None):
        """Descarga velas históricas (Klines)."""
        try:
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            if start_time:
                params['startTime'] = start_time

            return self.client.klines(**params)
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error descargando velas {interval}: {e}")
            return []

    # --- MÉTODOS DE EJECUCIÓN ---
    
    def place_order(self, params):
        """Envoltorio genérico para enviar órdenes."""
        try:
            return self.client.new_order(**params)
        except ClientError as e:
            self.log.registrar_error("API_MANAGER", f"Binance rechazó orden: {e.error_message}")
            return None
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error de ejecución: {e}")
            return None
    
    def cancel_order(self, symbol, order_id):
        """Cancela una orden específica de forma segura."""
        try:
            self.client.cancel_order(symbol=symbol, orderId=order_id)
            return True
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error cancelando orden {order_id}: {e}")
            return False

    def cancel_all_orders(self, symbol):
        try:
            self.client.cancel_open_orders(symbol=symbol)
        except Exception as e:
            self.log.registrar_error("API_MANAGER", f"Error cancelando órdenes: {e}")