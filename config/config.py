# =============================================================================
# UBICACIÓN: config/config.py
# DESCRIPCIÓN: CONFIGURACIÓN MAESTRA (V18.0 - GAMMA V4.6 LIVE)
# =============================================================================

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ---------------------------------------------------------
    # 1. IDENTIDAD Y CICLOS
    # ---------------------------------------------------------
    BOT_NAME = "SENTINEL PRO (GAMMA V4.6)"
    VERSION = "18.0-GAMMA-LIVE"
    
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
    MODE = 'TESTNET' # Cambiar a 'LIVE' para real
    
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
    TIMEFRAMES = ['3m', '5m', '15m', '30m', '1h', '4h', '1d']
    
    LEVERAGE = 5 
    MARGIN_TYPE = 'ISOLATED' 
    POSITION_MODE = 'HEDGE'

    # Precisión (valores base, se autocalibran en OrderManager)
    QTY_PRECISION = 1    
    PRICE_PRECISION = 2  

    # ---------------------------------------------------------
    # 5. GESTIÓN DE RIESGO GLOBAL
    # ---------------------------------------------------------
    MAX_RISK_SLOTS = 3        # REGLA: Máximo 3 operaciones simultáneas
    
    # Cupos por Estrategia (Prioridad absoluta a Gamma)
    MAX_GAMMA_SLOTS = 3       
    MAX_SWING_SLOTS = 0       # Inactivo (0 cupos)
    MAX_SHADOW_SLOTS = 0      # Inactivo (0 cupos)

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
    # 7. PARÁMETROS ESTRATEGIAS
    # ---------------------------------------------------------
    
    # Configuración Gamma V4.6 (Replica Exacta Simulador)
    class GammaConfig:
        # Gestión de Capital
        PCT_CAPITAL_PER_TRADE = 0.05  # 5% del capital por trade
        # Nota: Usamos el apalancamiento global (5x) para el cálculo de lotaje en Shooter
        
        # Filtros de Entrada
        RSI_PERIOD = 14
        FILTRO_DIST_FIBO_MAX = 0.008 # 0.8%
        
        # Filtros Hedge (Sniper)
        HEDGE_DIST_FIBO_MIN = 0.012  # 1.2%
        HEDGE_MACD_MAX = -0.01
        
        # Salidas (Hard Orders)
        SL_NORMAL = 0.020   # 2.0%
        SL_HEDGE = 0.015    # 1.5%
        
        TP_1_DIST = 0.035   # 3.5%
        TP_1_QTY = 0.40     # Vende 40% (ajustado a solicitud)
        
        TP_2_DIST = 0.045   # 4.5%
        TP_2_QTY = 0.30     # Vende 30% (ajustado a solicitud)
        
        # Gestión Dinámica (Comptroller)
        BE_ACTIVATION = 0.015  # Activa BE al 1.5% de ganancia
        BE_PROFIT = 0.005      # Asegura 0.5%
        TRAILING_DIST = 0.01   # Trailing del 1% (se activa tras TP1/BE)

    # Configuración Swing (Inactiva por ahora)
    class SwingConfig:
        RISK_USD_PER_TRADE = 30.0
        FILTRO_DIST_FIBO_MACRO = 0.025
        RSI_MAX_ENTRY = 35
        SL_INIT_NORMAL = 0.06
        TP1_DIST = 0.06; TP1_QTY_PCT = 0.50
        TP2_DIST = 0.12

    # Configuración Shadow (Inactiva por ahora)
    class ShadowConfig:
        BASE_UNIT_USD = 50.0 
        BB_PERIOD = 20; BB_STD_DEV = 2.0
        MIN_SPACING_ATR = 1.0
        MAX_SLOTS_PER_SIDE = 5
        CASHFLOW_TARGET_PCT = 0.80
        SHADOW_TRAILING_PCT = 0.05

    # ---------------------------------------------------------
    # 8. UTILIDADES
    # ---------------------------------------------------------
    @classmethod
    def inicializar_infraestructura(cls):
        for d in [cls.DIR_LOGS, cls.DIR_DATA, cls.DIR_MAPS]:
            if not os.path.exists(d):
                os.makedirs(d)