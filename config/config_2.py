import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """
    CENTRO DE COMANDO (CONFIG V12.2 - FIX ARRANQUE):
    Define reglas inmutables.
    - FIX: Restaurado 'inicializar_infraestructura' para compatibilidad con main.py.
    """
    
    # ---------------------------------------------------------
    # 1. IDENTIDAD Y SISTEMA (Requerido por main.py)
    # ---------------------------------------------------------
    BOT_NAME = "SENTINEL PRO (V12.0 REFINED)"
    VERSION = "12.0"
    
    # Ciclos de Reloj (Segundos)
    CYCLE_FAST = 1   # Auditoría y Trailing
    CYCLE_DASH = 3   # Dashboard
    CYCLE_SLOW = 10  # Análisis Brain
    
    # ---------------------------------------------------------
    # 2. CREDENCIALES
    # ---------------------------------------------------------
    API_KEY = os.getenv("BINANCE_API_KEY", "")
    API_SECRET = os.getenv("BINANCE_API_SECRET", "")
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # IMPORTANTE: True para Testnet, False para Real
    TESTNET = False  
    
    # ---------------------------------------------------------
    # 3. RUTAS
    # ---------------------------------------------------------
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DIR_LOGS = os.path.join(BASE_DIR, "logs")
    DIR_DATA = os.path.join(BASE_DIR, "data", "historical")
    
    # Archivos de logs (Compatibilidad Legacy)
    FILE_LOG_ERRORS = os.path.join(DIR_LOGS, 'bitacora_errores.csv')
    FILE_LOG_ACTIVITY = os.path.join(DIR_LOGS, 'bitacora_actividad.log')
    FILE_LOG_ORDERS = os.path.join(DIR_LOGS, 'bitacora_ordenes.csv')
    
    # ---------------------------------------------------------
    # 4. GENERAL MERCADO
    # ---------------------------------------------------------
    SYMBOL = "AAVEUSDT"
    TIMEFRAME = "15m"
    LEVERAGE = 5 
    MARGIN_TYPE = 'ISOLATED' 
    POSITION_MODE = 'HEDGE'
    
    # ---------------------------------------------------------
    # 5. ESTRATEGIA GAMMA (SCALPING - REFINADO)
    # ---------------------------------------------------------
    ENABLE_STRATEGY_GAMMA = True
    
    # Subclase para agrupar configuración Gamma
    class GammaConfig:
        # Gestión de Riesgo
        RISK_USD_FIXED = 15.0        
        # --- LÓGICA DE SALIDA DINÁMICA ---
        # Trailing Stop "Duro"
        GAMMA_TRAILING_ENABLED = True
        GAMMA_TRAILING_DIST_PCT = 0.015       # 1.5%
        GAMMA_TRAILING_UPDATE_MIN_PCT = 0.002 # 0.2%
        GAMMA_HARD_TP_PCT = 0.05              # 5%

    # ---------------------------------------------------------
    # 6. ESTRATEGIA SNIPER (SWING - INACTIVA)
    # ---------------------------------------------------------
    ENABLE_STRATEGY_SNIPER = False
    
    class SniperConfig:
        RISK_PER_TRADE = 0.05 
        STOP_LOSS_PCT = 0.05
        TP_PLAN = [
            {'dist': 0.06, 'qty_pct': 0.30, 'move_sl': 'BE'},
            {'dist': 0.09, 'qty_pct': 0.40, 'move_sl': 'TP1'},
            {'dist': 0.12, 'qty_pct': 0.30, 'move_sl': 'NONE'}
        ]

    # ---------------------------------------------------------
    # MÉTODOS DE SISTEMA (Vital para main.py)
    # ---------------------------------------------------------
    @classmethod
    def inicializar_infraestructura(cls):
        """
        Crea las carpetas necesarias antes de iniciar el bot.
        Llamado por main.py línea 53.
        """
        directorios = [cls.DIR_LOGS, cls.DIR_DATA, os.path.join(cls.BASE_DIR, 'tools')]
        for d in directorios:
            if not os.path.exists(d): os.makedirs(d)