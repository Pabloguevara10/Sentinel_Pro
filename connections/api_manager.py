# =============================================================================
# UBICACIÓN: connections/api_manager.py
# DESCRIPCIÓN: API MANAGER V19.5 (AUTO-SYNC TIME DRIFT FIX)
# =============================================================================

import time
import logging
from binance.um_futures import UMFutures
from binance.error import ClientError
from config.config import Config

class APIManager:
    def __init__(self, logger=None):
        self.log = logger
        self.client = None
        self.time_offset = 0
        self.last_sync_time = 0
        self.SYNC_INTERVAL = 3600  # Resincronizar cada 1 hora (3600s)
        self.trading_active = False 
        
        # Inicialización
        self._conectar_inicial()

    def _conectar_inicial(self):
        print("[API] 📡 Iniciando conexión...")
        try:
            base_url = 'https://testnet.binancefuture.com' if Config.TESTNET else 'https://fapi.binance.com'
            self.client = UMFutures(
                key=Config.API_KEY, 
                secret=Config.API_SECRET,
                base_url=base_url,
                timeout=20
            )
            self._sincronizar_reloj(forzar=True)
            self._configurar_margen()
            self.trading_active = True
            print("[API] ✅ Sistema Listo para Operar.")
            if self.log: self.log.registrar_actividad("API", "Conexión Exitosa y Sincronizada.")

        except Exception as e:
            print(f"❌ [API] Error Fatal Init: {e}")
            if self.log: self.log.registrar_error("API", f"Error Init: {e}")

    def _sincronizar_reloj(self, forzar=False):
        """Calcula el offset entre la PC y Binance para evitar Error -1021."""
        now = time.time()
        # Solo sincroniza si pasó 1 hora o se fuerza (por error)
        if forzar or (now - self.last_sync_time > self.SYNC_INTERVAL):
            try:
                server_time = int(self.client.time()['serverTime'])
                local_time = int(now * 1000)
                self.time_offset = server_time - local_time
                self.last_sync_time = now
                # Solo imprimimos si el salto es grande para no ensuciar el log
                if abs(self.time_offset) > 1000:
                    print(f"⏱️ [API] Reloj Resincronizado. Offset: {self.time_offset}ms")
            except Exception as e:
                print(f"⚠️ [API] Fallo al sincronizar tiempo: {e}")

    def _get_corrected_timestamp(self):
        # Chequeo rutinario de resincronización antes de cada firma
        self._sincronizar_reloj() 
        return int(time.time() * 1000) + self.time_offset

    def _configurar_margen(self):
        try:
            # Timestamp fresco
            ts = self._get_corrected_timestamp()
            
            # Hedge Mode
            try:
                self.client.change_position_mode(dualSidePosition="true", timestamp=ts)
            except ClientError as e:
                if e.error_code != -4059: pass # Ignorar "No need to change"

            # Leverage
            try:
                self.client.change_leverage(symbol=Config.SYMBOL, leverage=Config.LEVERAGE, timestamp=ts)
            except ClientError: pass
            
        except Exception as e:
            print(f"⚠️ [API] Nota Config: {e}")

    # --- MÉTODOS PÚBLICOS DE LECTURA ---
    def get_klines(self, symbol, interval, limit=1000, startTime=None):
        try:
            params = {'symbol': symbol, 'interval': interval, 'limit': limit}
            if startTime: params['startTime'] = startTime
            return self.client.klines(**params)
        except Exception as e:
            print(f"⚠️ [API] Error descarga: {e}")
            return []

    def get_ticker_price(self, symbol):
        try: 
            return float(self.client.ticker_price(symbol=symbol)['price'])
        except: return 0.0

    # --- EJECUCIÓN CON AUTO-RETRY ---
    def execute_generic_order(self, params):
        if not self.trading_active: return False, "API_NOT_READY"
        
        # Intento con auto-corrección de tiempo
        for intento in range(2): 
            try:
                params['timestamp'] = self._get_corrected_timestamp()
                return True, self.client.new_order(**params)
            
            except ClientError as e:
                # Si es error de Timestamp (-1021), forzamos resync y reintentamos UNA vez
                if e.error_code == -1021 and intento == 0:
                    print(f"🔧 [API] Detectado Error de Tiempo (-1021). Resincronizando y reintentando...")
                    self._sincronizar_reloj(forzar=True)
                    continue # Vuelve al loop
                return False, f"{e.error_code}: {e.error_message}"
                
            except Exception as e:
                return False, str(e)
        return False, "MAX_RETRIES_EXCEEDED"

    def place_market_order(self, symbol, side, qty, position_side=None, reduce_only=False):
        if not self.trading_active: return None
        try:
            params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': float(qty),
                'timestamp': self._get_corrected_timestamp()
            }
            if position_side: params['positionSide'] = position_side
            if reduce_only: params['reduceOnly'] = 'true'
            
            return self.client.new_order(**params)
        except Exception as e:
            raise e

    def get_position_info(self, symbol):
        if not self.trading_active: return None
        try:
            # Fix de lectura: timestamp actualizado
            params = {'symbol': symbol, 'timestamp': self._get_corrected_timestamp()}
            return self.client.get_position_risk(**params)
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