# =============================================================================
# UBICACIÓN: config/config.py
# DESCRIPCIÓN: CONFIGURACIÓN MAESTRA (V17.8 - TRIAD SYNC)
# =============================================================================

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ---------------------------------------------------------
    # 1. IDENTIDAD Y CICLOS
    # ---------------------------------------------------------
    BOT_NAME = "SENTINEL PRO (HYBRID ECOSYSTEM)"
    VERSION = "17.8-TRIAD-LIVE"
    
    CYCLE_FAST = 1   # Segundos (Latido)
    CYCLE_DASH = 3   # Segundos (Visual)
    CYCLE_SLOW = 10  # Segundos (Estrategia)
    
    # ---------------------------------------------------------
    # 2. RUTAS DE SISTEMA
    # ---------------------------------------------------------
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DIR_LOGS = os.path.join(BASE_DIR, "logs")
    DIR_DATA = os.path.join(BASE_DIR, "data", "historical")
    DIR_MAPS = os.path.join(DIR_DATA, "mapas_fvg")
    
    # Archivos de Logs
    FILE_LOG_ACTIVITY = os.path.join(DIR_LOGS, "activity.log")
    FILE_LOG_ERRORS = os.path.join(DIR_LOGS, "error.log")
    FILE_LOG_ORDERS = os.path.join(DIR_LOGS, "orders.csv")
    
    # ---------------------------------------------------------
    # 3. CREDENCIALES Y MODO
    # ---------------------------------------------------------
    MODE = 'TESTNET' # 'LIVE' o 'TESTNET'
    
    if MODE == 'TESTNET':
        API_KEY = os.getenv('BINANCE_API_KEY_TESTNET')
        API_SECRET = os.getenv('BINANCE_API_SECRET_TESTNET')
        TESTNET = True
    else:
        API_KEY = os.getenv('BINANCE_API_KEY_REAL')
        API_SECRET = os.getenv('BINANCE_API_SECRET_REAL')
        TESTNET = False

    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # ---------------------------------------------------------
    # 4. MERCADO
    # ---------------------------------------------------------
    SYMBOL = "AAVEUSDT"
    TIMEFRAMES = ["15m", "1h", "4h"] # TFs requeridos por la Tríada
    
    LEVERAGE = 5 
    MARGIN_TYPE = 'ISOLATED' 
    POSITION_MODE = 'HEDGE' # Vital

    # Precisión (valores base, se autocalibran)
    QTY_PRECISION = 1    
    PRICE_PRECISION = 2  

    # ---------------------------------------------------------
    # 5. GESTIÓN DE RIESGO GLOBAL
    # ---------------------------------------------------------
    MAX_RISK_SLOTS = 5        # Total cupos globales
    MAX_GAMMA_SLOTS = 2       # Límite Gamma
    MAX_SWING_SLOTS = 2       # Límite Swing
    MAX_SHADOW_SLOTS = 5      # Límite Shadow (Grid)

    # ---------------------------------------------------------
    # 6. PROTOCOLO DE EJECUCIÓN
    # ---------------------------------------------------------
    class ExecutionConfig:
        POLLING_INTERVAL = 0.5
        MAX_WAIT_TO_FILL = 45
        RETRY_DELAY = 0.8
        MAX_RETRIES_ORDER = 3
        MAX_RETRIES_SL = 5
        MIN_NOTIONAL_VALUE = 5.1
        DUPLICATE_DISTANCE_PCT = 0.001

    # ---------------------------------------------------------
    # 7. PARÁMETROS ESTRATEGIAS (COPIA EXACTA SIMULADOR)
    # ---------------------------------------------------------
    
    # Configuración Gamma V7 (Scalping)
    class GammaConfig:
        INITIAL_CAPITAL_ALLOCATION = 1000 # Referencia para cálculo proporcional si se requiere
        RISK_USD_PER_TRADE = 20.0 # O usar % del capital
        
        # Filtros
        RSI_PERIOD = 14
        FILTRO_DIST_FIBO_MAX = 0.008
        FILTRO_MACD_MIN = 0.0
        HEDGE_DIST_FIBO_MIN = 0.012
        HEDGE_MACD_MAX = -0.01
        
        # Salidas
        TP_NORMAL = 0.035; SL_NORMAL = 0.020
        TP_HEDGE = 0.045;  SL_HEDGE = 0.015
        
        # Trailing (Sim Logic)
        TRAILING_ACTIVATION = 0.015 # 1.5% ganancia para activar
        TRAILING_OFFSET = 0.005     # 0.5% distancia del precio

    # Configuración Swing V3 (Estructural)
    class SwingConfig:
        RISK_USD_PER_TRADE = 30.0
        
        # Filtros
        FILTRO_DIST_FIBO_MACRO = 0.025
        RSI_MAX_ENTRY = 35 # rsi < 35
        
        # Salidas
        SL_INIT_NORMAL = 0.06
        TP1_DIST = 0.06; TP1_QTY_PCT = 0.50 # Cerrar 50% al 6%
        TP2_DIST = 0.12

    # Configuración Shadow V2 (Mean Reversion)
    class ShadowConfig:
        BASE_UNIT_USD = 50.0 # Tamaño por entrada
        
        # Bollinger
        BB_PERIOD = 20
        BB_STD_DEV = 2.0
        
        # Grid Logic
        MIN_SPACING_ATR = 1.0
        MAX_SLOTS_PER_SIDE = 5
        
        # Salidas
        CASHFLOW_TARGET_PCT = 0.80 # % del ancho de banda
        SHADOW_TRAILING_PCT = 0.05 # 5% retroceso desde el pico de PnL

    # ---------------------------------------------------------
    # 8. UTILIDADES
    # ---------------------------------------------------------
    @classmethod
    def inicializar_infraestructura(cls):
        for d in [cls.DIR_LOGS, cls.DIR_DATA, cls.DIR_MAPS]:
            if not os.path.exists(d):
                os.makedirs(d)