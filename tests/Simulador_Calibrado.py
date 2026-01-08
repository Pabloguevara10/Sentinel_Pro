# =============================================================================
# UBICACIÓN: tests/Simulador_Calibrado.py
# DESCRIPCIÓN: Simulador con AJUSTES FORENSES (ATR Filter + SL 2.2%)
# ESTADO: FIXED (Variables Hedge Restauradas)
# =============================================================================

import pandas as pd
import numpy as np
import os
import warnings

warnings.filterwarnings('ignore')

# =============================================================================
# 1. NUEVA CONFIGURACIÓN (Basada en Auditoría Forense)
# =============================================================================
class ConfigSim:
    SYMBOL = "AAVEUSDT"
    CAPITAL_INICIAL = 1000.0
    LEVERAGE = 5 
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_FILE = os.path.join(BASE_DIR, "data", "historical", f"{SYMBOL}_1m.csv")
    
    # --- AJUSTES DE CALIBRACIÓN ---
    PCT_CAPITAL_PER_TRADE = 0.05
    
    # Filtros de Entrada (Brain)
    RSI_PERIOD = 14
    FILTRO_DIST_FIBO_MAX = 0.008 
    
    # Variables HEDGE (Restauradas)
    HEDGE_DIST_FIBO_MIN = 0.012
    HEDGE_MACD_MAX = -0.01
    
    # NUEVO: FILTRO DE VOLATILIDAD (ATR)
    # Solo operamos si el ATR (14) es mayor a 1.5 USD
    MIN_ATR_REQUIRED = 1.5 
    
    # Gestión de Salida (Optimizada según Forense)
    SL_NORMAL = 0.022   # Subido a 2.2% (Cubría el 90% de ganadoras)
    SL_HEDGE = 0.018    # Subido a 1.8%
    
    TP_1_DIST = 0.015   # 1.5% (TP Rápido)
    TP_1_QTY = 0.50     # Vender mitad
    
    TP_2_DIST = 0.035   # 3.5% (TP Largo)
    TP_2_QTY = 0.50     # Vender resto

# =============================================================================
# 2. HERRAMIENTAS
# =============================================================================
class StructureScanner:
    def __init__(self, df):
        self.df = df.copy()
        
    def precompute(self):
        window = 5
        self.df['max_roll'] = self.df['high'].rolling(window=window*2+1, center=True).max()
        self.df['min_roll'] = self.df['low'].rolling(window=window*2+1, center=True).min()
        self.df['is_pivot_high'] = (self.df['high'] == self.df['max_roll'])
        self.df['is_pivot_low'] = (self.df['low'] == self.df['min_roll'])
        self.df.drop(columns=['max_roll', 'min_roll'], inplace=True)

    def get_fibonacci_context(self, current_ts):
        try:
            past_df = self.df.loc[:current_ts].iloc[:-1]
            if past_df.empty: return None
            
            highs = past_df[past_df['is_pivot_high']]
            lows = past_df[past_df['is_pivot_low']]
            if highs.empty or lows.empty: return None

            last_h = float(highs.iloc[-1]['high'])
            last_l = float(lows.iloc[-1]['low'])
            
            fibs = {}
            diff = abs(last_h - last_l)
            if diff == 0: return None
            
            # Niveles genéricos cercanía
            if last_h > last_l: # Sube -> Retroceso
                fibs = {k: last_h - (diff * v) for k, v in {'0.382':0.382, '0.5':0.5, '0.618':0.618}.items()}
            else: # Baja -> Rebote
                fibs = {k: last_l + (diff * v) for k, v in {'0.382':0.382, '0.5':0.5, '0.618':0.618}.items()}
            return {'fibs': fibs}
        except: return None

# =============================================================================
# 3. MOTOR DE CÁLCULO (Con ATR)
# =============================================================================
def preparar_indicadores(df):
    cols = [c.lower() for c in df.columns]
    
    # RSI
    if 'rsi' not in cols:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 0.0001)
        df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    if 'macd_hist' not in cols:
        k = df['close'].ewm(span=12).mean(); d = df['close'].ewm(span=26).mean()
        df['macd_hist'] = (k - d) - (k - d).ewm(span=9).mean()
        
    # ATR (Vital para el nuevo filtro)
    if 'atr' not in cols:
        h_l = df['high'] - df['low']
        h_pc = (df['high'] - df['close'].shift(1)).abs()
        l_pc = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()
        
    return df.dropna()

# =============================================================================
# 4. SIMULADOR CALIBRADO
# =============================================================================
class SimuladorCalibrado:
    def __init__(self):
        print(f"🚀 Iniciando Simulador CALIBRADO (V3): {ConfigSim.SYMBOL}")
        print(f"⚙️ Filtro ATR > {ConfigSim.MIN_ATR_REQUIRED} | SL: {ConfigSim.SL_NORMAL*100}% | TP1: {ConfigSim.TP_1_DIST*100}%")
        
        try:
            self.df_1m = pd.read_csv(ConfigSim.DATA_FILE)
            self._limpiar_raw()
            print(f"✅ Data 1m: {len(self.df_1m)} velas.")
        except Exception as e: print(f"❌ Error: {e}"); exit()

        print("⏳ Generando entorno 15m/1H...")
        self.df_15m = self.df_1m.resample('15min', closed='right', label='right').agg(
            {'open':'first', 'high':'max', 'low':'min', 'close':'last'}).dropna()
        self.df_1h = self.df_1m.resample('1h', closed='right', label='right').agg(
            {'open':'first', 'high':'max', 'low':'min', 'close':'last'}).dropna()
            
        self.df_15m = preparar_indicadores(self.df_15m)
        self.df_1h = preparar_indicadores(self.df_1h)
        
        self.scanner = StructureScanner(self.df_1h)
        self.scanner.precompute()
        
        self.capital = ConfigSim.CAPITAL_INICIAL; self.posicion = None; self.historial = []
        self.rechazos_atr = 0

    def _limpiar_raw(self):
        self.df_1m.columns = [c.lower().strip() for c in self.df_1m.columns]
        if 'close' not in self.df_1m.columns:
             self.df_1m.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume'][:len(self.df_1m.columns)]
        
        col_time = 'timestamp' if 'timestamp' in self.df_1m.columns else 'time'
        first_val = self.df_1m[col_time].iloc[0]
        if isinstance(first_val, (int, float, np.integer)) and first_val > 1000000000000:
            self.df_1m[col_time] = pd.to_datetime(self.df_1m[col_time], unit='ms')
        else:
            self.df_1m[col_time] = pd.to_datetime(self.df_1m[col_time])
            
        self.df_1m.set_index(col_time, inplace=True)
        for c in ['open','high','low','close']: self.df_1m[c] = pd.to_numeric(self.df_1m[c], errors='coerce')
        self.df_1m.dropna(inplace=True)

    def ejecutar(self):
        print("\n▶️ RUNNING...")
        for ts, row in self.df_1m.iterrows():
            if self.posicion: self._check_exit(ts, row)
            
            if ts.minute % 15 == 0 and not self.posicion:
                self._check_entry(ts)
        self._reporte()

    def _get_dist(self, ts):
        try:
            idx_1h = self.df_1h.index.asof(ts)
            ctx = self.scanner.get_fibonacci_context(idx_1h)
            if not ctx: return 999
            price = self.df_1h.loc[idx_1h]['close']
            dists = [abs(price - v)/price for v in ctx['fibs'].values()]
            return min(dists)
        except: return 999

    def _check_entry(self, ts):
        if ts not in self.df_15m.index: return
        row = self.df_15m.loc[ts]
        
        # --- FILTRO 1: VOLATILIDAD (ATR) ---
        if row['atr'] < ConfigSim.MIN_ATR_REQUIRED:
            self.rechazos_atr += 1
            return # Mercado muerto, no operamos

        rsi = row['rsi']; dist = self._get_dist(ts)
        sig = None; mode = ""; cfg = ConfigSim
        
        # --- ESTRATEGIA ---
        if rsi < 30 and dist < cfg.FILTRO_DIST_FIBO_MAX:
            sig = 'LONG'; mode = 'NORM'; slp = cfg.SL_NORMAL
        elif rsi > 70 and dist < cfg.FILTRO_DIST_FIBO_MAX:
            sig = 'SHORT'; mode = 'NORM'; slp = cfg.SL_NORMAL
        elif rsi < 25 and dist > ConfigSim.HEDGE_DIST_FIBO_MIN and row['macd_hist'] < ConfigSim.HEDGE_MACD_MAX:
            sig = 'SHORT'; mode = 'HEDGE'; slp = cfg.SL_HEDGE

        if sig:
            self._open(sig, ts, row['close'], slp, mode)
            print(f"✅ ENTRY [{ts}] {sig} @ {row['close']:.2f} | ATR: {row['atr']:.2f}")

    def _open(self, side, time, price, sl_pct, mode):
        cfg = ConfigSim
        if side == 'LONG':
            sl = price*(1-sl_pct); tp1=price*(1+cfg.TP_1_DIST); tp2=price*(1+cfg.TP_2_DIST)
        else:
            sl = price*(1+sl_pct); tp1=price*(1-cfg.TP_1_DIST); tp2=price*(1-cfg.TP_2_DIST)
        
        self.posicion = {
            'side': side, 'entry_price': price, 'entry_time': time, 'sl': sl, 'tp1': tp1, 'tp2': tp2,
            'tp1_hit': False, 'size': self.capital * cfg.PCT_CAPITAL_PER_TRADE * cfg.LEVERAGE
        }

    def _check_exit(self, ts, row):
        pos = self.posicion
        h = row['high']; l = row['low']
        reason = None; pnl = 0
        cfg = ConfigSim
        
        if pos['side'] == 'LONG':
            if l <= pos['sl']: 
                reason='SL'; pnl=(pos['sl']-pos['entry_price'])/pos['entry_price']
            elif h >= pos['tp2']: 
                reason='TP2'
                # Profit mixto: 50% al TP1, 50% al TP2. Promediamos la ganancia
                gain_tp1 = cfg.TP_1_DIST
                gain_tp2 = cfg.TP_2_DIST
                pnl = (gain_tp1 * cfg.TP_1_QTY) + (gain_tp2 * cfg.TP_2_QTY)
                
            elif h >= pos['tp1'] and not pos['tp1_hit']: 
                pos['tp1_hit']=True; pos['sl']=pos['entry_price']*1.001 # Breakeven
        else:
            if h >= pos['sl']: 
                reason='SL'; pnl=(pos['entry_price']-pos['sl'])/pos['entry_price']
            elif l <= pos['tp2']: 
                reason='TP2'
                gain_tp1 = cfg.TP_1_DIST
                gain_tp2 = cfg.TP_2_DIST
                pnl = (gain_tp1 * cfg.TP_1_QTY) + (gain_tp2 * cfg.TP_2_QTY)
                
            elif l <= pos['tp1'] and not pos['tp1_hit']: 
                pos['tp1_hit']=True; pos['sl']=pos['entry_price']*0.999 # Breakeven
            
        if reason:
            usd = pos['size'] * pnl
            self.capital += usd
            self.historial.append({'exit': ts, 'pnl': usd, 'reason': reason})
            self.posicion = None

    def _reporte(self):
        if not self.historial: print("\n⚠️ 0 Trades."); return
        df = pd.DataFrame(self.historial)
        wins = df[df['pnl']>0]
        
        print("\n" + "="*40)
        print(f"📊 REPORTE CALIBRADO (ATR > {ConfigSim.MIN_ATR_REQUIRED})")
        print(f"💰 FINAL: ${self.capital:,.2f}")
        print(f"📈 ROI:   ${self.capital - ConfigSim.CAPITAL_INICIAL:,.2f}")
        print(f"🎲 Trades: {len(df)} (Win: {len(wins)/len(df)*100:.1f}%)")
        print(f"🚫 Señales rechazadas por Baja Volatilidad: {self.rechazos_atr}")
        print("="*40)
        df.to_csv(os.path.join(os.path.dirname(__file__), "Resultado_Calibrado.csv"), index=False)

if __name__ == "__main__":
    SimuladorCalibrado().ejecutar()