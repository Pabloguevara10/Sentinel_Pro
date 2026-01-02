# =============================================================================
# UBICACIÓN: connections/api_manager.py
# DESCRIPCIÓN: API MANAGER V17.6 (NULL SIGNAL ON FAIL)
# =============================================================================

import time
from binance.um_futures import UMFutures
from binance.error import ClientError
from config.config import Config

class APIManager:
    """
    DEPARTAMENTO DE COMUNICACIONES V17.6:
    - Retorna 'None' explícito en fallos de lectura para proteger la memoria local.
    """
    def __init__(self, logger):
        self.log = logger
        self.client = None
        self._conectar_y_validar()

    def _conectar_y_validar(self):
        try:
            if Config.TESTNET:
                base_url = 'https://testnet.binancefuture.com'
                self._log_msg("📡 Conectando a TESTNET...")
            else:
                base_url = 'https://fapi.binance.com'
                self._log_msg("🚨 Conectando a LIVE (REAL)...")

            self.client = UMFutures(
                key=Config.API_KEY, 
                secret=Config.API_SECRET,
                base_url=base_url
            )
            
            # Diagnóstico simple
            try:
                self.client.time()
            except: pass

            self._configurar_cuenta()
            self._log_msg("✅ Conexión OK.")

        except Exception as e:
            self._log_err(f"Fallo Crítico Conexión: {e}")
            raise e

    def _configurar_cuenta(self):
        try:
            try: self.client.change_position_mode(dualSidePosition='true')
            except: pass
            try: self.client.change_margin_type(symbol=Config.SYMBOL, marginType=Config.MARGIN_TYPE)
            except: pass
            try: self.client.change_leverage(symbol=Config.SYMBOL, leverage=Config.LEVERAGE)
            except: pass
        except: pass

    def _log_msg(self, msg):
        if hasattr(self.log, 'registrar_actividad'): self.log.registrar_actividad("API", msg)
        else: print(f"[API] {msg}")

    def _log_err(self, msg):
        if hasattr(self.log, 'registrar_error'): self.log.registrar_error("API", msg)
        else: print(f"[API ERROR] {msg}")

    # =========================================================================
    # MÉTODOS DE CONSULTA (PROTECTED)
    # =========================================================================
    
    def get_open_orders(self, symbol):
        """
        Intenta leer órdenes. Si falla por error de librería, retorna None.
        Esto avisa a Financials que NO debe borrar el libro local.
        """
        try:
            return self.client.get_open_orders(symbol=symbol)
        except Exception as e:
            # Logueamos el error pero retornamos None para proteger la memoria
            # No enviamos log de error a consola para no spamear, solo interno si fuera necesario
            return None 

    def get_position_info(self, symbol):
        try:
            positions = self.client.get_position_risk(symbol=symbol)
            if not positions: return None
            
            if isinstance(positions, list):
                target = next((p for p in positions if float(p.get('positionAmt', 0)) != 0), None)
                return target if target else positions[0]
            return positions
        except Exception:
            return None

    def execute_generic_order(self, params):
        try:
            return True, self.client.new_order(**params)
        except Exception as e:
            return False, str(e)

    def cancel_order(self, symbol, order_id):
        try:
            self.client.cancel_order(symbol=symbol, orderId=order_id)
            return True
        except: return False

    def cancel_all_open_orders(self, symbol):
        try:
            self.client.cancel_open_orders(symbol=symbol)
            return True
        except: return False
    
    def get_ticker_price(self, symbol):
        try:
            return float(self.client.ticker_price(symbol=symbol)['price'])
        except: return 0.0
        
    def get_account_balance(self):
        try:
            res = self.client.balance()
            for b in res:
                if b['asset'] == 'USDT': return float(b['balance'])
            return 0.0
        except: return 0.0