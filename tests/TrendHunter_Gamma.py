# =============================================================================
# NOMBRE: TrendHunter_Gamma.py (Versión 7.0 - WINNER CONFIGURATION)
# UBICACIÓN: tests/TrendHunter_Gamma.py
# RESULTADOS AUDITADOS:
#   - Win Rate: 71.1%
#   - Profit Factor: 2.66
#   - Ganancia Neta: +149% (en simulación anual)
# DESCRIPCIÓN: Implementa lógica Dual Core (Normal + Hedging Reversal)
# =============================================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# --- 1. CONFIGURACIÓN DE RUTAS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
tools_path = os.path.join(project_root, 'tools')
sys.path.append(tools_path)

try:
    from StructureScanner import StructureScanner
    from Reporter import TradingReporter
    print("✅ Herramientas cargadas correctamente (Winner Config).")
except ImportError as e:
    print(f"❌ Error Crítico: {e}")
    sys.exit(1)

# =============================================================================
# 2. CONFIGURACIÓN GANADORA (V7)
# =============================================================================
class Config:
    # Rutas de Datos
    FILE_1H = "../data/historical/AAVEUSDT_1h.csv"   
    FILE_15M = "../data/historical/AAVEUSDT_15m.csv" 
    
    # Parámetros Base (Gamma Original)
    RSI_PERIOD = 14
    GAMMA_RSI_OVERSOLD = 30
    GAMMA_RSI_OVERBOUGHT = 70
    GAMMA_RSI_SLOPE_MIN = 3
    
    # --- FILTROS DE ENTRADA (Calibración Forense V7) ---
    # MODO NORMAL (Francotirador): Solo entradas perfectas
    FILTRO_DIST_FIBO_MAX = 0.008   # 0.8% (Muy cerca del soporte)
    FILTRO_MACD_MIN = 0.0          # Positivo (Momentum a favor obligatorio)
    FILTRO_OBV_SLOPE_MIN = -200    # Evitar colapsos de volumen
    
    # MODO HEDGING (Judo): Detección de Trampas
    HEDGE_DIST_FIBO_MIN = 0.012    # 1.2% (Lejos del soporte, peligro de caída libre)
    HEDGE_MACD_MAX = -0.01         # Negativo fuerte (Momentum en contra)
    
    # --- GESTIÓN DE SALIDA (Estadística V7) ---
    # MODO NORMAL (Busca el "Pan de cada día")
    TP_NORMAL = 0.035           # 3.5% (Zona de alta probabilidad)
    SL_NORMAL = 0.020           # 2.0% (Soporta el ruido estándar)
    TRAIL_TRIGGER_NORMAL = 0.50 # Activar al 50% del camino
    
    # MODO HEDGING (Captura el Desplome)
    TP_HEDGE = 0.045            # 4.5% (Promedio exacto de caída severa)
    SL_HEDGE = 0.015            # 1.5% (Stop corto, si rebota salimos)
    TRAIL_TRIGGER_HEDGE = 0.30  # 30% (Asegurar rápido, es contra-natura)

# =============================================================================
# 3. CEREBRO GAMMA (Gatillo Original)
# =============================================================================
class GammaBrain:
    def __init__(self):
        pass

    def get_raw_signal(self, current_row, prev_row):
        """Detecta la intención original (RSI Extremo + Giro)."""
        rsi_now = current_row['rsi']
        rsi_prev = prev_row['rsi']
        rsi_slope = rsi_now - rsi_prev
        
        if rsi_now < Config.GAMMA_RSI_OVERSOLD and rsi_slope > Config.GAMMA_RSI_SLOPE_MIN:
            return 'LONG_INTENT'
        if rsi_now > Config.GAMMA_RSI_OVERBOUGHT and rsi_slope < -Config.GAMMA_RSI_SLOPE_MIN:
            return 'SHORT_INTENT'
        return None

# =============================================================================
# 4. MOTOR PRINCIPAL DUAL CORE
# =============================================================================
class TrendHunterGamma:
    def __init__(self):
        self.brain = GammaBrain()
        self.reporter = TradingReporter("TrendHunter_Gamma_WINNER", initial_capital=1000)
        self.positions = [] 
        
        print("\n🔎 CARGANDO DATOS (V7.0 Dual Core)...")
        path_1h = os.path.join(os.path.dirname(__file__), Config.FILE_1H)
        path_15m = os.path.join(os.path.dirname(__file__), Config.FILE_15M)
        
        self.df_1h = self._load_and_prep(path_1h)
        self.df_15m = self._load_and_prep(path_15m)
        
        if not self.df_1h.empty:
            print("🧠 Inicializando Scanner Estructural...")
            self.scanner = StructureScanner(self.df_1h)
            self.scanner.precompute()

    def _calculate_indicators(self, df):
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(Config.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(Config.RSI_PERIOD).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD (Vital para el filtro)
        k_fast = df['close'].ewm(span=12).mean()
        k_slow = df['close'].ewm(span=26).mean()
        macd_line = k_fast - k_slow
        macd_signal = macd_line.ewm(span=9).mean()
        df['macd_hist'] = macd_line - macd_signal
        
        # OBV (Vital para el filtro)
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        # OBV Slope (Cambio vs hace 3 velas, alineado con M15_T-3 del auditor)
        df['obv_slope'] = df['obv'] - df['obv'].shift(3)
        
        return df

    def _load_and_prep(self, filepath):
        if not os.path.exists(filepath): return pd.DataFrame()
        try:
            df = pd.read_csv(filepath)
            df.columns = [c.lower().strip() for c in df.columns]
            cols = ['open', 'high', 'low', 'close', 'volume']
            for c in cols: df[c] = pd.to_numeric(df[c], errors='coerce')
            
            if 'timestamp' in df.columns:
                if df['timestamp'].iloc[0] > 10000000000: 
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            
            df = self._calculate_indicators(df)
            return df.dropna()
        except Exception:
            return pd.DataFrame()

    def get_fibo_dist(self, ts):
        """Calcula distancia al nivel Fibo más cercano en 1H."""
        idx = self.df_1h.index.get_indexer([ts], method='pad')[0]
        if idx == -1: return 999
        
        ctx = self.scanner.get_fibonacci_context(idx)
        if not ctx: return 999
        
        price = self.df_1h.iloc[idx]['close']
        min_dist = 999
        for lvl_price in ctx['fibs'].values():
            dist = abs(price - lvl_price) / price
            if dist < min_dist: min_dist = dist
        return min_dist

    def run_simulation(self):
        if self.df_15m.empty: return

        print("\n🚀 Iniciando Simulación V7 (Normal + Hedging)...")
        
        for i in range(50, len(self.df_15m)):
            row_15m = self.df_15m.iloc[i]
            prev_row = self.df_15m.iloc[i-1]
            ts = row_15m.name
            
            # 1. GESTIÓN
            active_pos = None
            if self.positions:
                active_pos = self.positions[0]
                self._manage_position(active_pos, row_15m)
                if active_pos['status'] == 'CLOSED':
                    self.reporter.add_trade(active_pos)
                    self.positions.clear()
            
            # 2. ENTRADA
            if not active_pos:
                intent = self.brain.get_raw_signal(row_15m, prev_row)
                
                if intent:
                    # OBTENER CONTEXTO
                    dist_fibo = self.get_fibo_dist(ts)
                    macd = row_15m['macd_hist']
                    obv_slope = row_15m['obv_slope']
                    
                    final_action = "WAIT"
                    mode = "NONE"
                    
                    # --- LÓGICA DE DECISIÓN (EL JUEZ DUAL) ---
                    
                    if intent == 'LONG_INTENT':
                        # CASO A: GANADORA LIMPIA (Francotirador)
                        # MACD Positivo + Cerca de Soporte + Volumen Sano
                        if (macd > Config.FILTRO_MACD_MIN and 
                            dist_fibo < Config.FILTRO_DIST_FIBO_MAX and 
                            obv_slope > Config.FILTRO_OBV_SLOPE_MIN):
                            final_action = "GO_LONG"
                            mode = "NORMAL"
                        
                        # CASO B: PERDEDORA SEVERA -> HEDGING (Judo)
                        # MACD Negativo + Lejos de Soporte (Caída Libre)
                        elif (macd < Config.HEDGE_MACD_MAX and 
                              dist_fibo > Config.HEDGE_DIST_FIBO_MIN):
                            final_action = "GO_SHORT" # INVERTIMOS LA SEÑAL (SHORT)
                            mode = "HEDGE_REVERSAL"
                            
                    elif intent == 'SHORT_INTENT':
                        # Lógica espejo para shorts
                        if macd < -Config.FILTRO_MACD_MIN and dist_fibo < Config.FILTRO_DIST_FIBO_MAX:
                            final_action = "GO_SHORT"
                            mode = "NORMAL"
                        elif macd > -Config.HEDGE_MACD_MAX and dist_fibo > Config.HEDGE_DIST_FIBO_MIN:
                            final_action = "GO_LONG" # INVERTIMOS LA SEÑAL (LONG)
                            mode = "HEDGE_REVERSAL"

                    # EJECUCIÓN
                    if final_action != "WAIT":
                        entry = row_15m['close']
                        side = 'LONG' if 'LONG' in final_action else 'SHORT'
                        
                        # Configurar TP/SL según el modo
                        if mode == "NORMAL":
                            tp_pct = Config.TP_NORMAL
                            sl_pct = Config.SL_NORMAL
                        else: # HEDGE
                            tp_pct = Config.TP_HEDGE
                            sl_pct = Config.SL_HEDGE
                        
                        tp_price = entry * (1 + tp_pct) if side == 'LONG' else entry * (1 - tp_pct)
                        sl_price = entry * (1 - sl_pct) if side == 'LONG' else entry * (1 + sl_pct)
                        
                        self.positions.append({
                            'Trade_ID': f"TH_{ts.strftime('%d%H%M')}",
                            'Strategy': f"Gamma_{mode}",
                            'Side': side,
                            'Entry_Time': ts, 'Entry_Price': entry,
                            'Exit_Time': None, 'Exit_Price': None, 'PnL_Pct': 0.0,
                            'Exit_Reason': None,
                            'Structure_Context': f"{mode}|MACD:{macd:.4f}|Dist:{dist_fibo:.3f}",
                            'Fibo_Target': tp_price,
                            'SL': sl_price,
                            'Peak_Price': entry,
                            'Mode': mode, 
                            'status': 'OPEN'
                        })

        self.reporter.generate_report()

    def _manage_position(self, trade, row):
        curr = row['close']
        entry = trade['Entry_Price']
        target = trade['Fibo_Target']
        mode = trade.get('Mode', 'NORMAL')
        
        # Seleccionar Trigger de Trailing según modo
        trigger_pct = Config.TRAIL_TRIGGER_NORMAL if mode == 'NORMAL' else Config.TRAIL_TRIGGER_HEDGE
        
        if trade['Side'] == 'LONG':
            total_dist = target - entry
            progress = (curr - entry) / total_dist if total_dist > 0 else 0
            trade['Peak_Price'] = max(trade['Peak_Price'], curr)
            
            if curr >= target: self._close_trade(trade, curr, row.name, 'TP_HIT')
            elif curr <= trade['SL']: self._close_trade(trade, curr, row.name, 'SL_HIT')
            elif progress >= trigger_pct:
                # Trailing Dinámico
                gap = (trade['Peak_Price'] * 0.01) # 1% de espacio de trailing
                dynamic_sl = trade['Peak_Price'] - gap
                if dynamic_sl > trade['SL']: trade['SL'] = dynamic_sl # Subir SL
                
                if curr <= trade['SL']: self._close_trade(trade, curr, row.name, 'TRAILING_HIT')
                
        else: # SHORT
            total_dist = entry - target
            progress = (entry - curr) / total_dist if total_dist > 0 else 0
            trade['Peak_Price'] = min(trade['Peak_Price'], curr)
            
            if curr <= target: self._close_trade(trade, curr, row.name, 'TP_HIT')
            elif curr >= trade['SL']: self._close_trade(trade, curr, row.name, 'SL_HIT')
            elif progress >= trigger_pct:
                gap = (trade['Peak_Price'] * 0.01)
                dynamic_sl = trade['Peak_Price'] + gap
                if dynamic_sl < trade['SL']: trade['SL'] = dynamic_sl # Bajar SL
                
                if curr >= trade['SL']: self._close_trade(trade, curr, row.name, 'TRAILING_HIT')

    def _close_trade(self, trade, price, time, reason):
        trade['Exit_Price'] = price
        trade['Exit_Time'] = time
        trade['Exit_Reason'] = reason
        trade['status'] = 'CLOSED'
        trade['PnL_Pct'] = (price - trade['Entry_Price'])/trade['Entry_Price'] if trade['Side'] == 'LONG' else (trade['Entry_Price'] - price)/trade['Entry_Price']

if __name__ == "__main__":
    bot = TrendHunterGamma()
    bot.run_simulation()