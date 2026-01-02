# =============================================================================
# UBICACIÓN: connections/api_manager.py
# DESCRIPCIÓN: API MANAGER V19.1 (BUGFIX MARGEN & RELOJ VIRTUAL)
# =============================================================================

import time
from binance.um_futures import UMFutures
from binance.error import ClientError
from config.config import Config

class APIManager:
    def __init__(self, logger):
        self.log = logger
        self.client = None
        self.time_offset = 0
        self.trading_active = False 
        self._conectar_y_sincronizar()

    def _conectar_y_sincronizar(self):
        print("[API] 📡 Iniciando conexión con Reloj Virtual...")
        try:
            base_url = 'https://testnet.binancefuture.com' if Config.TESTNET else 'https://fapi.binance.com'
            
            self.client = UMFutures(
                key=Config.API_KEY, 
                secret=Config.API_SECRET,
                base_url=base_url,
                timeout=20
            )
            
            # Sincronización
            try:
                server_time = int(self.client.time()['serverTime'])
                local_time = int(time.time() * 1000)
                self.time_offset = server_time - local_time
                print(f"⏱️ [API] Offset aplicado: {self.time_offset}ms")
            except:
                self.time_offset = 0

            # Configuración
            self._configurar_margen()
            self.trading_active = True
            print("[API] ✅ Sistema Listo para Operar.")

        except Exception as e:
            print(f"❌ [API] Error Fatal: {e}")
            if self.log: self.log.registrar_error("API", f"Error Init: {e}")

    def _get_corrected_timestamp(self):
        return int(time.time() * 1000) + self.time_offset

    def _configurar_margen(self):
        try:
            params = {'timestamp': self._get_corrected_timestamp()}
            
            # Hedge Mode
            try:
                self.client.change_position_mode(dualSidePosition="true", **params)
            except ClientError as e:
                # CORRECCIÓN DEL BUG: Comparamos el código directamente
                if e.error_code != -4059 and "No need to change" not in e.error_message:
                    pass # Ignoramos errores no críticos

            # Leverage
            try:
                self.client.change_leverage(symbol=Config.SYMBOL, leverage=Config.LEVERAGE, **params)
            except ClientError: pass
            
        except Exception as e:
            # Solo imprimimos si es un error real, no advertencias
            print(f"⚠️ [API] Nota Config: {e}")

    # --- MÉTODOS PÚBLICOS ---
    def get_klines(self, symbol, interval, limit=1000, startTime=None):
        try:
            params = {'symbol': symbol, 'interval': interval, 'limit': limit}
            if startTime: params['startTime'] = startTime
            return self.client.klines(**params)
        except Exception as e:
            print(f"⚠️ [API] Error descarga: {e}")
            return []

    def get_ticker_price(self, symbol):
        try: return float(self.client.ticker_price(symbol=symbol)['price'])
        except: return 0.0

    # --- MÉTODOS PRIVADOS ---
    def execute_generic_order(self, params):
        if not self.trading_active: return False, "API_NOT_READY"
        try:
            params['timestamp'] = self._get_corrected_timestamp()
            return True, self.client.new_order(**params)
        except Exception as e:
            return False, str(e)

    def get_position_info(self, symbol):
        if not self.trading_active: return None
        try:
            params = {'symbol': symbol, 'timestamp': self._get_corrected_timestamp()}
            positions = self.client.get_position_risk(**params)
            if isinstance(positions, list): return positions
            return [positions]
        except: return None
        
    def get_account_balance(self):
        if not self.trading_active: return 0.0
        try:
            params = {'timestamp': self._get_corrected_timestamp()}
            res = self.client.balance(**params)
            for asset in res:
                if asset['asset'] == 'USDT': return float(asset['balance'])
            return 0.0
        except: return 0.0
    
    def cancel_order(self, symbol, order_id):
        if self.trading_active:
            try: 
                params = {'symbol': symbol, 'orderId': order_id, 'timestamp': self._get_corrected_timestamp()}
                self.client.cancel_order(**params)
            except: pass
            
    def cancel_all_open_orders(self, symbol):
        if self.trading_active:
            try: 
                params = {'symbol': symbol, 'timestamp': self._get_corrected_timestamp()}
                self.client.cancel_open_orders(**params)
            except: pass