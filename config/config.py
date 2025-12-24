<<<<<<< HEAD
# =============================================================================
# UBICACIÓN: config/config.py
# DESCRIPCIÓN: CONFIGURACIÓN MAESTRA (HYBRID CORE V1.0) - FIX LOGS
# =============================================================================

=======
>>>>>>> 4c4d97b (commit 24/12)
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
<<<<<<< HEAD
    # ---------------------------------------------------------
    # 1. IDENTIDAD Y SISTEMA
    # ---------------------------------------------------------
    BOT_NAME = "SENTINEL PRO (HYBRID ECOSYSTEM)"
    VERSION = "13.5-INTEGRATED"
    
    # Ciclos de Reloj (Segundos)
    CYCLE_FAST = 1   # Auditoría y Trailing
    CYCLE_DASH = 3   # Dashboard
    CYCLE_SLOW = 10  # Análisis Brain / Generación Velas
    
    # ---------------------------------------------------------
    # 2. RUTAS DE SISTEMA (UNIFICADAS)
    # ---------------------------------------------------------
    # Base dir apunta a la raiz del proyecto
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Rutas estandarizadas
    DIR_LOGS = os.path.join(BASE_DIR, "logs")
    DIR_DATA = os.path.join(BASE_DIR, "data", "historical")
    DIR_MAPS = os.path.join(DIR_DATA, "mapas_fvg")
    
    # Alias para compatibilidad con código V13 (Brain)
    DATA_PATH = DIR_DATA 
    LOGS_PATH = DIR_LOGS
    
    # --- ARCHIVOS DE LOGS (CORREGIDO) ---
    FILE_LOG_ACTIVITY = os.path.join(DIR_LOGS, "activity.log")
    FILE_LOG_ERRORS = os.path.join(DIR_LOGS, "error.log")
    # ✅ ESTA ES LA LÍNEA QUE FALTABA:
    FILE_LOG_ORDERS = os.path.join(DIR_LOGS, "orders.csv")
    
    # ---------------------------------------------------------
    # 3. CREDENCIALES
    # ---------------------------------------------------------
    API_KEY = os.getenv("BINANCE_API_KEY", "")
    API_SECRET = os.getenv("BINANCE_API_SECRET", "")
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    TESTNET = False  # False = DINERO REAL
    
    # ---------------------------------------------------------
    # 4. MERCADO GENERAL
    # ---------------------------------------------------------
    SYMBOL = "AAVEUSDT"
    TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"]
    LIMIT_CANDLES = 1000
    
    # --- NUEVAS VARIABLES DE PRECISIÓN (Añadir esto) ---
    QTY_PRECISION = 1    # AAVE acepta 1 decimal (ej: 0.1)
    PRICE_PRECISION = 2  # AAVE precio con 2 decimales (ej: 198.45)
        
    # Configuración de Futuros (Heredado de V12 para Shooter)
    LEVERAGE = 5 
    MARGIN_TYPE = 'ISOLATED' 
    POSITION_MODE = 'HEDGE' # Vital para operar Long y Short simultáneos
    
    # ---------------------------------------------------------
    # 5. GESTIÓN DE RIESGO UNIFICADA (SLOTS)
    # ---------------------------------------------------------
    # Define cuántas operaciones simultáneas permitimos
    MAX_RISK_SLOTS = 3       
    MAX_GAMMA_SLOTS = 2      
    MAX_SWING_SLOTS = 2      

    # ---------------------------------------------------------
    # 6. INTERRUPTORES DE ESTRATEGIA (CENTRO DE MANDO)
    # ---------------------------------------------------------
    
    # --- MODOS ECOSISTEMA V13 (SIMULADOR) ---
    # Activos para operar con la nueva lógica probada
    ENABLE_ECO_GAMMA_V7 = True   # TrendHunter Gamma (Scalping)
    ENABLE_ECO_SWING_V3 = True   # SwingHunter Alpha (Estructural)
    
    # --- MODOS LEGACY V12 (RESPALDO) ---
    # Inactivos por defecto
    ENABLE_LEGACY_GAMMA = False
    ENABLE_LEGACY_SNIPER = False

    # ---------------------------------------------------------
    # 7. PARÁMETROS ESTRATEGIAS V13 (ECOSISTEMA)
    # ---------------------------------------------------------
    
    class GammaConfig:
        """Configuración para TrendHunter Gamma V7 (V13)"""
        RISK_USD_FIXED = 20.0  
        RSI_PERIOD = 14
        
        # Filtros de Entrada
        FILTRO_DIST_FIBO_MAX = 0.008   
        FILTRO_MACD_MIN = 0.0          
        HEDGE_DIST_FIBO_MIN = 0.012    
        HEDGE_MACD_MAX = -0.01         
        
        # Salidas Dinámicas
        TP_NORMAL = 0.035; SL_NORMAL = 0.020; TRAIL_TRIGGER_NORM = 0.50 
        TP_HEDGE = 0.045; SL_HEDGE = 0.015; TRAIL_TRIGGER_HEDGE = 0.30

        # Trailing Duro (Seguridad Shooter)
        GAMMA_TRAILING_ENABLED = True
        GAMMA_TRAILING_DIST_PCT = 0.015       
        GAMMA_HARD_TP_PCT = 0.05

    class SwingConfig:
        """Configuración para SwingHunter Alpha V3 (V13)"""
        RISK_USD_FIXED = 30.0 
        
        # Filtros
        FILTRO_DIST_FIBO_MACRO = 0.025
        FILTRO_MACD_MIN = 0.0
        HEDGE_DIST_FIBO_MIN = 0.050
        HEDGE_MACD_MAX = -0.05
        
        # Salidas Iniciales
        SL_INIT_NORMAL = 0.060; SL_INIT_HEDGE = 0.030
        
        # Plan Fraccionado (TP1, TP2, Runner)
        TP1_DIST = 0.06; TP1_QTY = 0.30 
        TP2_DIST = 0.12; TP2_QTY = 0.30 
        RUNNER_TRAIL_START = 0.15; RUNNER_GAP = 0.03
        TP_HEDGE_FULL = 0.08

    # ---------------------------------------------------------
    # 8. PARÁMETROS ESTRATEGIAS V12 (LEGACY)
    # ---------------------------------------------------------
    
    class LegacyGammaConfig:
        """Configuración antigua de Gamma (V12) - Para compatibilidad"""
        RISK_USD_FIXED = 15.0        
        GAMMA_TRAILING_ENABLED = True
        GAMMA_TRAILING_DIST_PCT = 0.015       
        GAMMA_TRAILING_UPDATE_MIN_PCT = 0.002 
        GAMMA_HARD_TP_PCT = 0.05              

    class LegacySniperConfig:
        """Configuración antigua de Sniper (V12) - Para compatibilidad"""
        RISK_PER_TRADE = 0.05 
        STOP_LOSS_PCT = 0.05
        TP_PLAN = [
            {'dist': 0.06, 'qty_pct': 0.30, 'move_sl': 'BE'},
            {'dist': 0.09, 'qty_pct': 0.40, 'move_sl': 'TP1'},
            {'dist': 0.12, 'qty_pct': 0.30, 'move_sl': 'NONE'}
        ]

    # ---------------------------------------------------------
    # 9. UTILS DEL SISTEMA
    # ---------------------------------------------------------
    @classmethod
    def inicializar_infraestructura(cls):
        """Crea todas las carpetas necesarias al arranque"""
        directorios = [cls.DIR_LOGS, cls.DIR_DATA, cls.DIR_MAPS]
        for d in directorios:
            if not os.path.exists(d):
                try:
                    os.makedirs(d)
                    print(f"📁 Directorio creado: {d}")
                except Exception as e:
                    print(f"❌ Error creando directorio {d}: {e}")
=======
    """
    Configuración Sentinel AI Pro V8.4 (FULL RESTORED).
    ---------------------------------------------------
    - Restaura variables Legacy (Sección 10) que se borraron accidentalmente.
    - Incluye SH_BASE_UNIT_USD (Sección 11) para el CLI.
    - Mantiene toda la lógica ShadowHunter V2.
    """
    
    # =========================================================================
    # 0. CONFIGURACIÓN DE DATOS
    # =========================================================================
    TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h']

    # =========================================================================
    # 1. IDENTIDAD Y DUALIDAD
    # =========================================================================
    BOT_NAME = "SENTINEL PRO (SHADOW V2 - CLI READY)"
    VERSION = "8.4.0"
    
    # MODO: 'TESTNET' (Pruebas) | 'LIVE' (Dinero Real)
    MODE = 'TESTNET' 

    # Compatibilidad Legacy
    TESTNET = True if MODE == 'TESTNET' else False

    # Selección Automática de Llaves
    if MODE == 'TESTNET':
        API_KEY = os.getenv('BINANCE_API_KEY_TESTNET')
        API_SECRET = os.getenv('BINANCE_API_SECRET_TESTNET')
        if not API_KEY: API_KEY = os.getenv('BINANCE_API_KEY')
        if not API_SECRET: API_SECRET = os.getenv('BINANCE_API_SECRET')
        print(f"⚠️  MODO ACTIVO: TESTNET (Simulación Conectada)")
    else:
        API_KEY = os.getenv('BINANCE_API_KEY_REAL')
        API_SECRET = os.getenv('BINANCE_API_SECRET_REAL')
        if not API_KEY or not API_SECRET:
            raise ValueError("❌ ERROR: Faltan CREDENCIALES REALES en .env")
        print(f"🚨 MODO ACTIVO: LIVE (Operación Real ShadowHunter)")

    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # =========================================================================
    # 2. CICLOS DE EJECUCIÓN
    # =========================================================================
    REQUEST_TIMEOUT = 20
    MAX_RETRIES = 3
    
    SYNC_CYCLE_FAST = 1    
    SYNC_CYCLE_SLOW = 10   
    SYNC_CYCLE_SCAN = 300  
    
    CYCLE_FAST = SYNC_CYCLE_FAST
    CYCLE_SLOW = SYNC_CYCLE_SLOW
    CYCLE_DASH = 3

    # =========================================================================
    # 3. CAPITAL Y GESTIÓN GENERAL
    # =========================================================================
    SYMBOL = 'AAVEUSDT'   
    LEVERAGE = 5          
    LOG_LEVEL = 'INFO'

    USE_FIXED_CAPITAL = True
    FIXED_CAPITAL_AMOUNT = 2000.0  
    MAX_DAILY_LOSS_PCT = 0.05
    DAILY_TARGET_PCT = 0.08
    MAX_OPEN_POSITIONS = 5  

    # =========================================================================
    # 4. ESTRATEGIA PRINCIPAL: SHADOW HUNTER V2
    # =========================================================================
    class ShadowConfig:
        ENABLED = True
        NAME = "SHADOW_HUNTER_V2"
        ALLOCATION_PCT = 0.50  # $1000 asignados
        
        # Gatillos
        ENTRY_RSI_LONG = 30    
        ENTRY_RSI_SHORT = 70   
        
        # Gestión de Posición
        MAX_DCA_LAYERS = 3     
        DCA_MULTIPLIER = 1.5   
        DCA_STEP_PCT = 0.02    
        
        # Salidas
        TAKE_PROFIT_PCT = 0.015 
        STOP_LOSS_PCT = 0.10    

    # =========================================================================
    # 5. ECOSISTEMA (BRAIN & SHOOTER)
    # =========================================================================
    class BrainConfig:
        USE_4H_TREND_FILTER = True
        STOCH_1H_OVERBOUGHT = 80 
        STOCH_1H_OVERSOLD = 20
        ADX_MIN_STRENGTH = 20.0
        SCALP_BB_WIDTH_MIN = 0.40   
        TREND_ADX_MIN = 25.0
        FVG_TIMEFRAMES = ['15m', '1h', '4h']

    class ShooterConfig:
        MODES = {
            'SNIPER_FVG': {
                'wallet_pct': 0.25, 'stop_loss_pct': 0.05, 'take_profit_pct': 0.12,
                'entry_offset_pct': 0.003, 'take_profit_type': 'FIXED_LEVELS'
            },
            'TREND_FOLLOWING': {
                'wallet_pct': 0.15, 'stop_loss_pct': 0.035, 'take_profit_pct': 0.10,
                'entry_offset_pct': 0.0, 'take_profit_type': 'FIXED_LEVELS' 
            },
            'SCALP_BB': {
                'wallet_pct': 0.05, 'stop_loss_pct': 0.02, 'take_profit_pct': 0.025,
                'entry_offset_pct': 0.0, 'take_profit_type': 'DYNAMIC_BB'
            },
            'MANUAL': {
                'wallet_pct': 0.05, 'stop_loss_pct': 0.02, 'take_profit_pct': 0.04,
                'entry_offset_pct': 0.0, 'take_profit_type': 'FIXED_LEVELS'
            }
        }
        TP_DISTANCES = [0.015, 0.030, 0.060] 
        TP_SPLIT = [0.30, 0.40, 0.30] 
        BE_TRIGGER_PCT = 0.015
        DCA_ENABLED = False 
        DCA_MAX_ADDS = 0
        DCA_TRIGGER_DIST_PCT = 0.0
        DCA_MULTIPLIER = 1.0

    # =========================================================================
    # 6. RUTAS DEL SISTEMA
    # =========================================================================
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOGS_DIR = os.path.join(BASE_DIR, 'logs')
    DIR_LOGS = LOGS_DIR             
    DIR_DATA = os.path.join(LOGS_DIR, 'data_lab')
    DATA_DIR = DIR_DATA             
    BITACORA_DIR = os.path.join(LOGS_DIR, 'bitacoras')
    LOG_PATH = BITACORA_DIR         
    DIR_MAPS = os.path.join(DIR_DATA, "mapas_fvg") 

    FILE_STATE = os.path.join(BITACORA_DIR, 'bot_state.json')
    FILE_METRICS = os.path.join(BITACORA_DIR, 'metrics_history.csv')
    FILE_WALLET = os.path.join(BITACORA_DIR, 'virtual_wallet.json')
    FILE_ORDERS = os.path.join(BITACORA_DIR, 'orders_positions.csv')
    FILE_ERRORS = os.path.join(BITACORA_DIR, 'system_errors.csv')
    FILE_ACTIVITY = os.path.join(BITACORA_DIR, 'bot_activity.log')
    
    FILE_LOG_ACTIVITY = FILE_ACTIVITY  
    FILE_LOG_ERRORS = FILE_ERRORS      
    FILE_LOG_ORDERS = FILE_ORDERS      
    DATA_PATH = DIR_DATA               

    # =========================================================================
    # 7. PERFILES DE RIESGO
    # =========================================================================
    TRADING_MODE = 'SECURE' 
    PROFILES = {
        'SECURE': {
            'risk_per_trade': 0.01, 'sl_buffer': 0.003,
            'max_vwap_dist': 1.5, 'tp_logic': 'INSTITUCIONAL'
        },
        'AGGRESSIVE': {
            'risk_per_trade': 0.02, 'sl_buffer': 0.0,
            'max_vwap_dist': 3.0, 'tp_logic': 'RUNNER'
        }
    }
    @property
    def ACTIVE_PROFILE(self):
        return self.PROFILES[self.TRADING_MODE]
>>>>>>> 4c4d97b (commit 24/12)

    # =========================================================================
    # 8. LEGACY & UTILS
    # =========================================================================
    S_TP1_DIST = 0.015 
    S_TP2_DIST = 0.030
    S_TP1_QTY = 0.5
    S_TP2_QTY = 0.5

    class LegacyGammaConfig:
        RISK_USD_FIXED = 5.0        
        GAMMA_TRAILING_ENABLED = True
        GAMMA_TRAILING_DIST_PCT = 0.015       
        GAMMA_TRAILING_UPDATE_MIN_PCT = 0.002 
        GAMMA_HARD_TP_PCT = 0.05              

    class LegacySniperConfig:
        RISK_PER_TRADE = 0.05 
        STOP_LOSS_PCT = 0.05
        TP_PLAN = [{'dist': 0.06, 'qty_pct': 0.30, 'move_sl': 'BE'}]

    # =========================================================================
    # 10. VARIABLES LEGACY (RESTAURADAS)
    # =========================================================================
    # Estas son las que se borraron por error en V8.3
    ENABLE_SHADOW_V2 = True 
    ENABLE_ECO_SWING_V3 = False 
    ENABLE_ECO_GAMMA_V7 = False 

    # =========================================================================
    # 11. CONSTANTES SHADOW CLI (AGREGADAS)
    # =========================================================================
    # Variable para inyecciones manuales vía CLI
    SH_BASE_UNIT_USD = 50.0  

    @classmethod
    def inicializar_infraestructura(cls):
        directorios = [cls.DIR_LOGS, cls.DIR_DATA, cls.BITACORA_DIR, cls.DIR_MAPS]
        for d in directorios:
            if not os.path.exists(d):
                try:
                    os.makedirs(d)
                    print(f"📁 Directorio creado: {d}")
                except: pass

Config.inicializar_infraestructura()