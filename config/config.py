import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """
    GERENCIA CENTRAL: Define las reglas inmutables del ecosistema.
    VERSION: 11.5 (Panel de Control de Estrategias)
    """
    # --- 1. IDENTIDAD Y CREDENCIALES ---
    BOT_NAME = "SENTINEL PRO V11.5 (SWITCH PANEL)"
    API_KEY = os.getenv('BINANCE_API_KEY', '')
    API_SECRET = os.getenv('BINANCE_API_SECRET', '')
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # --- 2. REGLAS OPERATIVAS ---
    SYMBOL = 'AAVEUSDT'
    LEVERAGE = 5
    MARGIN_TYPE = 'ISOLATED' 
    POSITION_MODE = 'HEDGE'  
    MAX_DAILY_LOSS_PCT = 0.05
    
    # Ciclos de Reloj
    CYCLE_FAST = 1
    CYCLE_DASH = 3
    CYCLE_SLOW = 10

    # --- 3. CONTROL DE ESTRATEGIAS (INTERRUPTORES) ---
    # Configura True/False para activar/desactivar lógicas sin borrar código.
    ENABLE_STRATEGY_SNIPER = False  # <--- DORMIDO (Modo Hibernación)
    ENABLE_STRATEGY_GAMMA = True    # <--- ACTIVO (Modo Operativo)

    # --- 4. PERFIL ESTRATÉGICO (SNIPER V11) ---
    class SniperConfig:
        RISK_PER_TRADE = 0.05    # 5% Riesgo por operación
        STOP_LOSS_PCT = 0.05     # 5% Distancia de SL
        
        # Plan de Salida Escalonada (TPs)
        TP_PLAN = [
            {'dist': 0.06, 'qty_pct': 0.30, 'move_sl': 'BE'},  # TP1: 6%
            {'dist': 0.09, 'qty_pct': 0.40, 'move_sl': 'TP1'}, # TP2: 9%
            {'dist': 0.12, 'qty_pct': 0.30, 'move_sl': 'NONE'} # TP3: 12%
        ]

    # --- 5. PERFIL ESTRATÉGICO (GAMMA SCALPING) ---
    class GammaConfig:
        """
        Configuración para Operativa de Alta Frecuencia (15m)
        """
        RISK_USD_FIXED = 100.0        # Riesgo monetario fijo ($50 USD)
        STOP_LOSS_PCT = 0.015        # 1.5% Stop Loss (Estricto)
        TP1_PCT = 0.05               # 5.0% Take Profit Estructural
        
        # Gestión Dinámica (Contralor)
        TP_DYNAMIC_THRESHOLD = 150.0 # Ganancia USD para activar cierre parcial
        TP_DYNAMIC_QTY_PCT = 0.25    # % de la posición a cerrar al tocar umbral
        
        # Smart Trailing (RSI 15m)
        RSI_TRAILING_DIST_NORMAL = 0.03   # 3% Trailing Normal
        RSI_TRAILING_DIST_EXTREME = 0.015 # 1.5% Trailing Apretado (Extremo)

    # --- 6. RUTAS ---
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DIR_LOGS = os.path.join(BASE_DIR, 'logs')
    FILE_LOG_ERRORS = os.path.join(DIR_LOGS, 'bitacora_errores.csv')
    FILE_LOG_ACTIVITY = os.path.join(DIR_LOGS, 'bitacora_actividad.log')
    FILE_LOG_ORDERS = os.path.join(DIR_LOGS, 'bitacora_ordenes.csv')
    DIR_DATA = os.path.join(BASE_DIR, 'data', 'historical')

    @classmethod
    def inicializar_infraestructura(cls):
        directorios = [cls.DIR_LOGS, cls.DIR_DATA, os.path.join(cls.BASE_DIR, 'tools')]
        for d in directorios:
            if not os.path.exists(d): os.makedirs(d)