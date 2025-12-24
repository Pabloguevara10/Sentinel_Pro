# =============================================================================
# UBICACIÓN: config/config.py
# DESCRIPCIÓN: CONFIGURACIÓN MAESTRA (HYBRID CORE V1.0) - FIX LOGS
# =============================================================================

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
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

    @staticmethod
    def validar_credenciales():
        return bool(Config.API_KEY and Config.API_SECRET)