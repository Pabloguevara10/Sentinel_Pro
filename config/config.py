# =============================================================================
# UBICACIÓN: config/config.py
# DESCRIPCIÓN: Configuración Maestra V13.2 (Fix Nombres de Variables)
# =============================================================================

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ---------------------------------------------------------
    # 1. IDENTIDAD Y SISTEMA
    # ---------------------------------------------------------
    BOT_NAME = "SENTINEL PRO (V13.2 DUAL CORE)"
    VERSION = "13.2"
    
    CYCLE_FAST = 1   
    CYCLE_DASH = 3   
    CYCLE_SLOW = 10  
    
    # --- RUTAS DE SISTEMA (COMPATIBILIDAD TOTAL) ---
    DATA_PATH = "data/historical"
    LOGS_PATH = "logs"
    
    # FIX: Definimos ambas versiones (Singular y Plural) para evitar errores
    FILE_LOG_ACTIVITY = os.path.join(LOGS_PATH, "activity.log")
    FILE_LOG_ACTIVITIES = os.path.join(LOGS_PATH, "activity.log") 
    
    FILE_LOG_ERROR = os.path.join(LOGS_PATH, "error.log")
    FILE_LOG_ERRORS = os.path.join(LOGS_PATH, "error.log") # <-- La que faltaba
    
    DB_FILE = os.path.join(DATA_PATH, "trading_history.db")
    
    # ---------------------------------------------------------
    # 2. CREDENCIALES
    # ---------------------------------------------------------
    API_KEY = os.getenv("BINANCE_API_KEY", "")
    API_SECRET = os.getenv("BINANCE_API_SECRET", "")
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    TESTNET = False  
    
    # ---------------------------------------------------------
    # 3. MERCADO
    # ---------------------------------------------------------
    SYMBOL = "AAVEUSDT"
    TIMEFRAMES = ["15m", "1h", "4h", "1d"] 
    LIMIT_CANDLES = 1000

    # ---------------------------------------------------------
    # 4. GESTIÓN DE RIESGO
    # ---------------------------------------------------------
    MAX_RISK_SLOTS = 3       
    MAX_GAMMA_SLOTS = 2      
    MAX_SWING_SLOTS = 2      
    
    # ---------------------------------------------------------
    # 5. ESTRATEGIA GAMMA V7 (SCALPING)
    # ---------------------------------------------------------
    ENABLE_STRATEGY_GAMMA = True
    
    class GammaConfig:
        RISK_USD_FIXED = 20.0  
        RSI_PERIOD = 14
        
        # Filtros
        FILTRO_DIST_FIBO_MAX = 0.008   
        FILTRO_MACD_MIN = 0.0          
        HEDGE_DIST_FIBO_MIN = 0.012    
        HEDGE_MACD_MAX = -0.01         
        
        # Salidas
        TP_NORMAL = 0.035; SL_NORMAL = 0.020; TRAIL_TRIGGER_NORM = 0.50 
        TP_HEDGE = 0.045; SL_HEDGE = 0.015; TRAIL_TRIGGER_HEDGE = 0.30

    # ---------------------------------------------------------
    # 6. ESTRATEGIA SWING V3 (FRACTIONAL)
    # ---------------------------------------------------------
    ENABLE_STRATEGY_SWING = True
    
    class SwingConfig:
        RISK_USD_FIXED = 30.0 
        
        # Filtros
        FILTRO_DIST_FIBO_MACRO = 0.025
        FILTRO_MACD_MIN = 0.0
        HEDGE_DIST_FIBO_MIN = 0.050
        HEDGE_MACD_MAX = -0.05
        
        # Salidas
        SL_INIT_NORMAL = 0.060; SL_INIT_HEDGE = 0.030
        
        # Plan Fraccionado
        TP1_DIST = 0.06; TP1_QTY = 0.30 
        TP2_DIST = 0.12; TP2_QTY = 0.30 
        RUNNER_TRAIL_START = 0.15; RUNNER_GAP = 0.03
        TP_HEDGE_FULL = 0.08

    # ---------------------------------------------------------
    # 7. UTILS
    # ---------------------------------------------------------
    @staticmethod
    def inicializar_infraestructura():
        try:
            os.makedirs(Config.DATA_PATH, exist_ok=True)
            os.makedirs(Config.LOGS_PATH, exist_ok=True)
            print("✅ Infraestructura V13.2 OK.")
        except Exception as e:
            print(f"❌ Error config sys: {e}")

    @staticmethod
    def validar_credenciales():
        return bool(Config.API_KEY and Config.API_SECRET)