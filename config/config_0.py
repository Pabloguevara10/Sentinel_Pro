# =============================================================================
# UBICACIÓN: config/config.py
# DESCRIPCIÓN: CONFIGURACIÓN ALTO RENDIMIENTO (10x - CAPITAL $2,000)
# CORRECCIÓN: Alias de compatibilidad para Shooter V15 y Gestión de Riesgo
# =============================================================================

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ---------------------------------------------------------
    # 1. IDENTIDAD Y SISTEMA
    # ---------------------------------------------------------
    BOT_NAME = "SENTINEL PRO (HIGH STAKES)"
    VERSION = "15.0-MAX"
    
    # Ciclos de Reloj (Segundos)
    CYCLE_FAST = 1   # Auditoría y Trailing
    CYCLE_DASH = 3   # Dashboard
    CYCLE_SLOW = 10  # Análisis Brain / Generación Velas
    
    # ---------------------------------------------------------
    # 2. RUTAS DE SISTEMA
    # ---------------------------------------------------------
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DIR_LOGS = os.path.join(BASE_DIR, "logs")
    DIR_DATA = os.path.join(BASE_DIR, "data", "historical")
    DIR_MAPS = os.path.join(DIR_DATA, "mapas_fvg")
    
    # Alias Compatibilidad
    DATA_PATH = DIR_DATA 
    LOGS_PATH = DIR_LOGS
    
    FILE_LOG_ACTIVITY = os.path.join(DIR_LOGS, "activity.log")
    FILE_LOG_ERRORS = os.path.join(DIR_LOGS, "error.log")
    FILE_LOG_ORDERS = os.path.join(DIR_LOGS, "orders.csv")
    
    # ---------------------------------------------------------
    # 3. CREDENCIALES
    # ---------------------------------------------------------
    API_KEY = os.getenv("BINANCE_API_KEY", "")
    API_SECRET = os.getenv("BINANCE_API_SECRET", "")
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    SYSTEM_MODE = 'LIVE' 
    TESTNET = False 
    
    # ---------------------------------------------------------
    # 4. MERCADO Y ACTIVOS
    # ---------------------------------------------------------
    SYMBOL = "AAVEUSDT"
    TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"]
    LIMIT_CANDLES = 1000 # Límite por petición API, no límite de histórico total
    
    # Precisión (AAVE)
    QTY_PRECISION = 1    
    PRICE_PRECISION = 2  
    MIN_QTY = 0.1
        
    # --- APALANCAMIENTO AGRESIVO (10x) ---
    LEVERAGE = 10
    MARGIN_TYPE = 'ISOLATED' 
    POSITION_MODE = 'HEDGE' 
    
    # ---------------------------------------------------------
    # 5. GESTIÓN DE RIESGO (CAPITAL $2,000)
    # ---------------------------------------------------------
    INITIAL_CAPITAL = 2000.0 # Referencia para cálculos
    
    MAX_RISK_TOTAL = 5       
    MAX_GAMMA_SLOTS = 2      
    MAX_SWING_SLOTS = 2      
    SH_MAX_SLOTS = 5         

    # ---------------------------------------------------------
    # 6. ESTRATEGIAS ACTIVAS
    # ---------------------------------------------------------
    ENABLE_ECO_GAMMA_V7 = True   
    ENABLE_ECO_SWING_V3 = True   
    ENABLE_SHADOW_V2 = True      
    
    ENABLE_LEGACY_GAMMA = False
    ENABLE_LEGACY_SNIPER = False

    # ---------------------------------------------------------
    # 7. PARÁMETROS DE ESTRATEGIA (Con Alias para Shooter V15)
    # ---------------------------------------------------------
    
    class GammaConfig:
        """TrendHunter Gamma V7"""
        RISK_USD_FIXED = 30.0 # 1.5% de 2000
        
        G_RSI_PERIOD = 14
        FILTRO_DIST_FIBO_MAX = 0.008   
        FILTRO_MACD_MIN = 0.0          
        HEDGE_DIST_FIBO_MIN = 0.040    
        HEDGE_MACD_MAX = -0.01         
        
        # Salidas
        TP_NORMAL = 0.035; SL_NORMAL = 0.020
        TP_HEDGE = 0.045; SL_HEDGE = 0.015
        
        # Trailing
        GAMMA_TRAILING_ENABLED = True
        GAMMA_TRAILING_DIST_PCT = 0.015       
        GAMMA_HARD_TP_PCT = 0.05
        G_TRAIL_NORM = 0.005 

    class SwingConfig:
        """SwingHunter Alpha V3"""
        RISK_USD_FIXED = 60.0 # 3% de 2000
        
        FILTRO_DIST_FIBO_MACRO = 0.025
        SL_INIT_NORMAL = 0.060
        
        TP1_DIST = 0.06; TP1_QTY = 0.30 
        TP2_DIST = 0.12; TP2_QTY = 0.30 

    class ShadowConfig:
        """ShadowHunter V2"""
        SH_BASE_UNIT_USD = 200.0 # Tamaño de entrada nominal   
        
        SH_BB_PERIOD = 20
        SH_BB_STD_DEV = 2.0
        SH_MIN_SPACING_ATR = 1.0   
        SH_TRAILING_PCT = 0.05     

    # --- ALIAS DE COMPATIBILIDAD (CRÍTICO PARA SHOOTER V15) ---
    # El Shooter busca estas variables en self.cfg.VARIABLE
    S_TP1_DIST = SwingConfig.TP1_DIST
    S_TP2_DIST = SwingConfig.TP2_DIST
    S_TP1_QTY = SwingConfig.TP1_QTY
    S_TP2_QTY = SwingConfig.TP2_QTY

    # ---------------------------------------------------------
    # 8. LEGACY
    # ---------------------------------------------------------
    class LegacyGammaConfig:
        RISK_USD_FIXED = 30.0        
        GAMMA_TRAILING_ENABLED = True
        GAMMA_TRAILING_DIST_PCT = 0.015       
        GAMMA_TRAILING_UPDATE_MIN_PCT = 0.002 
        GAMMA_HARD_TP_PCT = 0.05              

    class LegacySniperConfig:
        RISK_PER_TRADE = 0.05 
        STOP_LOSS_PCT = 0.05
        TP_PLAN = [{'dist': 0.06, 'qty_pct': 0.30, 'move_sl': 'BE'}]

    # ---------------------------------------------------------
    # 9. UTILS
    # ---------------------------------------------------------
    @classmethod
    def inicializar_infraestructura(cls):
        directorios = [cls.DIR_LOGS, cls.DIR_DATA, cls.DIR_MAPS]
        for d in directorios:
            if not os.path.exists(d):
                try:
                    os.makedirs(d)
                    print(f"📁 Directorio creado: {d}")
                except Exception as e:
                    print(f"❌ Error creando directorio {d}: {e}")

    @staticmethod
    def validar_credenciales():
        return bool(Config.API_KEY and Config.API_SECRET)