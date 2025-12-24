import os
from dotenv import load_dotenv

load_dotenv()

class Config:
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