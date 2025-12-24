# =============================================================================
# NOMBRE: Simon_Sentinel_Gold.py
# TIPO: Simulador de Alta Fidelidad (Golden Master)
# OBJETIVO: Validar estrategia Gamma V7 + Swing V3 con Data Histórica de 1 Año.
# CORRECCIONES:
#   - Estructura: Usa StructureScanner_2 (Fibo Context).
#   - Filtros: OBV Slope Suavizado (T-3) para evitar falsos positivos.
#   - Gestión: Trailing Dinámico del Bot Real.
# =============================================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# --- 1. CONFIGURACIÓN DE ENTORNO ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
tools_path = os.path.join(project_root, 'tools')
sys.path.append(tools_path)

try:
    # IMPORTANTE: Usamos la versión _2 que tiene la lógica Fibo ganadora
    from StructureScanner_2 import StructureScanner
    from Reporter import TradingReporter
    print("✅ Simon Sentinel: Herramientas Avanzadas (_2) cargadas.")
except ImportError as e:
    print(f"❌ Error Crítico: {e}")
    sys.exit(1)

# =============================================================================
# 2. CONFIGURACIÓN COMPATIBLE CON EL BOT (Parametrización)
# =============================================================================
class Config:
    # Rutas de Datos (Asegúrate de tener data de 1 año)
    FILE_1H = "../data/historical/AAVEUSDT_1h.csv"
    FILE_15M = "../data/historical/AAVEUSDT_15m.csv"
    
    # --- PARÁMETROS GAMMA V7 (SCALPING) ---
    G_RSI_PERIOD = 14
    G_RSI_OVERSOLD = 30
    G_RSI_OVERBOUGHT = 70
    
    # Filtros de Entrada (Modo Francotirador)
    G_FILTRO_DIST_FIBO_MAX = 0.008   # 0.8% Distancia máxima al nivel Fibo
    G_FILTRO_MACD_MIN = 0.0          # Momentum positivo
    G_FILTRO_OBV_SLOPE_MIN = -500    # Corrección OBV: Evitar caídas drásticas de volumen
    
    # Filtros Hedge (Modo Judo/Reversal)
    G_HEDGE_DIST_FIBO_MIN = 0.015    # 1.5% (Sobre-extendido)
    G_HEDGE_MACD_MAX = -0.01
    
    # Salidas Gamma
    G_TP_NORMAL = 0.035; G_SL_NORMAL = 0.020; G_TRAIL_TRIGGER = 0.50
    G_TP_HEDGE = 0.045;  G_SL_HEDGE = 0.015
    
    # Capital Inicial
    INITIAL_CAPITAL = 1000

# =============================================================================
# 3. PROCESADOR DE DATOS (Con Corrección OBV)
# =============================================================================
class DataProcessor:
    @staticmethod
    def prepare_data(df):
        df = df.copy()
        df.columns = [c.lower().strip() for c in df.columns]
        
        # 1. RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(Config.G_RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(Config.G_RSI_PERIOD).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 2. MACD
        k_fast = df['close'].ewm(span=12).mean()
        k_slow = df['close'].ewm(span=26).mean()
        macd_line = k_fast - k_slow
        macd_signal = macd_line.ewm(span=9).mean()
        df['macd_hist'] = macd_line - macd_signal
        
        # 3. OBV & OBV SLOPE (CORRECCIÓN)
        # Calculamos el OBV estándar
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        
        # Slope Suavizado: Diferencia vs hace 3 velas (T-3)
        # Esto elimina el ruido de 1 sola vela y muestra la tendencia real del volumen
        df['obv_slope'] = df['obv'].diff(3).fillna(0)
        
        return df.dropna()

# =============================================================================
# 4. MOTOR DE SIMULACIÓN (CEREBRO + EJECUCIÓN)
# =============================================================================
class SimonSentinel:
    def __init__(self):
        self.reporter = TradingReporter("Sentinel_Gold_1Year", initial_capital=Config.INITIAL_CAPITAL)
        self.positions = []
        self.scanner_1h = None
        
    def load_data(self):
        print("📂 Cargando Datos Históricos...")
        path_1h = os.path.join(os.path.dirname(__file__), Config.FILE_1H)
        path_15m = os.path.join(os.path.dirname(__file__), Config.FILE_15M)
        
        if not os.path.exists(path_1h) or not os.path.exists(path_15m):
            print("❌ Faltan archivos CSV en data/historical/")
            sys.exit(1)
            
        self.df_1h = DataProcessor.prepare_data(pd.read_csv(path_1h))
        self.df_15m = DataProcessor.prepare_data(pd.read_csv(path_15m))
        
        # Timestamp index
        for df in [self.df_1h, self.df_15m]:
            if 'timestamp' in df.columns:
                # Detección auto de formato ms o s
                if df['timestamp'].iloc[0] > 10000000000:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)

        # Inicializar Scanner Potente (_2)
        print("🧠 Inicializando StructureScanner V2 (Cálculo Fibo)...")
        self.scanner_1h = StructureScanner(self.df_1h)
        self.scanner_1h.precompute() # Esto genera el contexto histórico

    def get_fibo_context(self, ts):
        """Busca la distancia al nivel Fibo más cercano en 1H."""
        idx = self.df_1h.index.get_indexer([ts], method='pad')[0]
        if idx == -1: return 999
        
        # Usamos el método de StructureScanner_2
        ctx = self.scanner_1h.get_fibonacci_context(idx)
        if not ctx: return 999
        
        price = self.df_1h.iloc[idx]['close']
        min_dist = 999
        # Iterar niveles para hallar el más cercano
        for lvl_price in ctx['fibs'].values():
            dist = abs(price - lvl_price) / price
            if dist < min_dist: min_dist = dist
        return min_dist

    def run(self):
        if self.df_15m.empty: return
        print(f"🚀 Iniciando Simulación (Total Velas 15m: {len(self.df_15m)})...")
        
        # Iteramos vela a vela en 15m
        for i in range(50, len(self.df_15m)):
            row = self.df_15m.iloc[i]
            ts = row.name
            
            # 1. GESTIÓN DE POSICIONES (Trailing)
            if self.positions:
                active_trade = self.positions[0]
                self._manage_trade(active_trade, row)
                if active_trade['status'] == 'CLOSED':
                    self.reporter.add_trade(active_trade)
                    self.positions.clear()
                continue # Solo 1 operación a la vez para prueba pura
                
            # 2. BÚSQUEDA DE ENTRADAS (Gamma V7 Logic)
            self._check_entry(row, ts, i)
            
        self.reporter.generate_report()

    def _check_entry(self, row, ts, idx):
        # Datos
        rsi = row['rsi']
        prev_rsi = self.df_15m.iloc[idx-1]['rsi']
        rsi_slope = rsi - prev_rsi
        macd = row['macd_hist']
        obv_slope = row['obv_slope']
        
        # Contexto Estructural (El secreto)
        dist_fibo = self.get_fibo_context(ts)
        
        signal = None
        mode = "NONE"
        
        # --- LÓGICA LONG ---
        # Gatillo: RSI Sobreventa + Giro Rápido
        if rsi < Config.G_RSI_OVERSOLD and rsi_slope > 2:
            
            # Caso A: NORMAL (Trend Following)
            # Requiere: Estar cerca de soporte Fibo, MACD positivo, OBV sano
            if (dist_fibo < Config.G_FILTRO_DIST_FIBO_MAX and 
                macd > Config.G_FILTRO_MACD_MIN and 
                obv_slope > Config.G_FILTRO_OBV_SLOPE_MIN):
                signal = "LONG"; mode = "NORMAL"
                
            # Caso B: HEDGE (Reversal de Caída Libre)
            # Requiere: Estar LEJOS de soporte (caída extendida) y MACD muy negativo
            elif (dist_fibo > Config.G_HEDGE_DIST_FIBO_MIN and 
                  macd < Config.G_HEDGE_MACD_MAX):
                signal = "LONG"; mode = "HEDGE_REVERSAL" # Apostamos al rebote del gato muerto

        # --- LÓGICA SHORT ---
        elif rsi > Config.G_RSI_OVERBOUGHT and rsi_slope < -2:
            if (dist_fibo < Config.G_FILTRO_DIST_FIBO_MAX and 
                macd < -Config.G_FILTRO_MACD_MIN): # MACD Negativo
                signal = "SHORT"; mode = "NORMAL"
                
            elif (dist_fibo > Config.G_HEDGE_DIST_FIBO_MIN and 
                  macd > -Config.G_HEDGE_MACD_MAX):
                signal = "SHORT"; mode = "HEDGE_REVERSAL"

        # EJECUCIÓN
        if signal:
            self._open_position(ts, row['close'], signal, mode, dist_fibo)

    def _open_position(self, ts, price, side, mode, dist_context):
        tp_pct = Config.G_TP_NORMAL if mode == "NORMAL" else Config.G_TP_HEDGE
        sl_pct = Config.G_SL_NORMAL if mode == "NORMAL" else Config.G_SL_HEDGE
        
        tp_price = price * (1 + tp_pct) if side == 'LONG' else price * (1 - tp_pct)
        sl_price = price * (1 - sl_pct) if side == 'LONG' else price * (1 + sl_pct)
        
        trade = {
            'Trade_ID': f"SIM_{ts.strftime('%m%d%H%M')}",
            'Strategy': f"Gamma_{mode}",
            'Side': side,
            'Entry_Time': ts,
            'Entry_Price': price,
            'Exit_Time': None, 'Exit_Price': None, 'PnL_Pct': 0.0,
            'Exit_Reason': None,
            'Structure_Context': f"DistFibo:{dist_context:.4f}",
            'SL': sl_price,
            'TP': tp_price,
            'Peak_Price': price,
            'Mode': mode,
            'status': 'OPEN'
        }
        self.positions.append(trade)

    def _manage_trade(self, trade, row):
        curr = row['close']
        entry = trade['Entry_Price']
        side = trade['Side']
        
        # Actualizar Pico para Trailing
        if side == 'LONG': trade['Peak_Price'] = max(trade['Peak_Price'], curr)
        else: trade['Peak_Price'] = min(trade['Peak_Price'], curr)
        
        # 1. Chequeo Hard SL/TP
        if side == 'LONG':
            if curr >= trade['TP']: self._close(trade, curr, row.name, "TP_HIT")
            elif curr <= trade['SL']: self._close(trade, curr, row.name, "SL_HIT")
        else:
            if curr <= trade['TP']: self._close(trade, curr, row.name, "TP_HIT")
            elif curr >= trade['SL']: self._close(trade, curr, row.name, "SL_HIT")
            
        if trade['status'] == 'CLOSED': return

        # 2. Trailing Stop Dinámico
        # Si vamos ganando X% del recorrido, subimos el SL
        total_dist = abs(trade['TP'] - entry)
        current_gain = abs(curr - entry)
        progress = current_gain / total_dist if total_dist > 0 else 0
        
        if progress >= Config.G_TRAIL_TRIGGER:
            gap = entry * 0.005 # Dejar 0.5% de aire
            if side == 'LONG':
                new_sl = curr - gap
                if new_sl > trade['SL']: trade['SL'] = new_sl
            else:
                new_sl = curr + gap
                if new_sl < trade['SL']: trade['SL'] = new_sl

    def _close(self, trade, price, time, reason):
        trade['Exit_Price'] = price
        trade['Exit_Time'] = time
        trade['Exit_Reason'] = reason
        trade['status'] = 'CLOSED'
        if trade['Side'] == 'LONG':
            trade['PnL_Pct'] = (price - trade['Entry_Price']) / trade['Entry_Price']
        else:
            trade['PnL_Pct'] = (trade['Entry_Price'] - price) / trade['Entry_Price']

if __name__ == "__main__":
    sim = SimonSentinel()
    sim.load_data()
    sim.run()