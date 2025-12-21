# =============================================================================
# NOMBRE: Sniper_Omega_V2.py (Quality Filter + Fractional Exit)
# UBICACIÓN: tests/Sniper_Omega_V2.py
# =============================================================================
import pandas as pd
import numpy as np
import os
import sys

# --- CONFIGURACIÓN ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
tools_path = os.path.join(project_root, 'tools')
sys.path.append(tools_path)

try:
    from StructureScanner import StructureScanner
    from Reporter import TradingReporter
except:
    pass

class Config:
    FILE_MACRO = "../data/historical/AAVEUSDT_1h.csv"
    FILE_MICRO = "../data/historical/AAVEUSDT_1m.csv"
    
    # FILTROS
    MIN_BB_WIDTH = 0.02
    ZONE_TOLERANCE = 0.003
    
    # GESTIÓN
    TP1_QTY = 0.60
    TP2_QTY = 0.20
    SL_FIXED_PCT = 0.01

class SniperOmegaV2:
    def __init__(self):
        try:
            self.reporter = TradingReporter("Sniper_V2_Quality", initial_capital=1000)
        except:
            self.reporter = None
        self.positions = [] 
        
        print("\n🎯 SNIPER V2: Cargando Datos...")
        self.df_macro = self._load_csv(Config.FILE_MACRO)
        self.df_micro = self._load_csv(Config.FILE_MICRO)
        
        if not self.df_macro.empty:
            self.scanner = StructureScanner(self.df_macro)
            self.scanner.precompute()

    def _load_csv(self, path_rel):
        path = os.path.join(os.path.dirname(__file__), path_rel)
        if not os.path.exists(path): return pd.DataFrame()
        df = pd.read_csv(path)
        df.columns = [c.lower().strip() for c in df.columns]
        if 'timestamp' in df.columns:
            if df['timestamp'].iloc[0] > 10000000000:
                 df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            else:
                 df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
        # Indicadores Micro (BB + RSI)
        if '1m' in path_rel:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            sma = df['close'].rolling(20).mean()
            std = df['close'].rolling(20).std()
            df['bb_upper'] = sma + (std * 2)
            df['bb_lower'] = sma - (std * 2)
            df['bb_mid'] = sma
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
            
        return df.dropna()

    def get_macro_zone(self, ts):
        idx = self.df_macro.index.get_indexer([ts], method='pad')[0]
        if idx == -1: return 999
        ctx = self.scanner.get_fibonacci_context(idx)
        if not ctx: return 999
        price = self.df_macro.iloc[idx]['close']
        min_dist = 999
        for lvl in ctx['fibs'].values():
            d = abs(price - lvl) / price
            if d < min_dist: min_dist = d
        return min_dist

    def run(self):
        if self.df_micro.empty: return
        print(f"🔭 SNIPER V2: Vigilando {len(self.df_micro)} minutos...")
        
        for i in range(50, len(self.df_micro)):
            row = self.df_micro.iloc[i]
            ts = row.name
            
            if self.positions:
                self._manage(self.positions[0], row)
                if self.positions[0]['status'] == 'CLOSED':
                    if self.reporter: self.reporter.add_trade(self.positions[0])
                    self.positions.clear()
                continue
            
            # FILTROS DE ENTRADA
            if row['bb_width'] < Config.MIN_BB_WIDTH: continue
            
            dist = self.get_macro_zone(ts)
            if dist < Config.ZONE_TOLERANCE:
                signal = None
                if row['rsi'] < 25: signal = 'GO_LONG'
                elif row['rsi'] > 75: signal = 'GO_SHORT'
                
                if signal:
                    entry = row['close']
                    side = 'LONG' if signal == 'GO_LONG' else 'SHORT'
                    sl = entry * (1 - Config.SL_FIXED_PCT) if side == 'LONG' else entry * (1 + Config.SL_FIXED_PCT)
                    
                    self.positions.append({
                        'Trade_ID': f"SN_{ts.strftime('%d%H%M')}",
                        'Strategy': 'Sniper_Quality',
                        'Side': side,
                        'Entry_Time': ts, 'Entry_Price': entry,
                        'Exit_Time': None, 'Exit_Price': None, 'PnL_Pct': 0.0,
                        'Exit_Reason': None,
                        'SL': sl, 'Peak_Price': entry,
                        'status': 'OPEN',
                        'Rem_Qty': 1.0, 'TP1_Hit': False, 'TP2_Hit': False
                    })
        
        if self.reporter: self.reporter.generate_report()

    def _manage(self, trade, row):
        # Misma lógica de gestión que FlashV2
        curr = row['close']
        entry = trade['Entry_Price']
        side = trade['Side']
        mid = row['bb_mid']
        upper = row['bb_upper']
        lower = row['bb_lower']
        band_range = upper - lower
        
        if side == 'LONG':
            tp1_price = mid
            tp2_price = lower + (band_range * 0.75)
            
            if curr <= trade['SL']:
                self._close(trade, curr, row.name, 'SL_HIT')
                return
            if not trade['TP1_Hit'] and curr >= tp1_price:
                trade['TP1_Hit'] = True
                trade['Rem_Qty'] -= Config.TP1_QTY
                trade['SL'] = entry 
            if not trade['TP2_Hit'] and curr >= tp2_price:
                trade['TP2_Hit'] = True
                trade['Rem_Qty'] -= Config.TP2_QTY
                trade['SL'] = tp1_price
            if trade['TP2_Hit']:
                trade['Peak_Price'] = max(trade['Peak_Price'], curr)
                dyn_sl = trade['Peak_Price'] * 0.995
                if dyn_sl > trade['SL']: trade['SL'] = dyn_sl
                
        else: # SHORT
            tp1_price = mid
            tp2_price = upper - (band_range * 0.75)
            
            if curr >= trade['SL']:
                self._close(trade, curr, row.name, 'SL_HIT')
                return
            if not trade['TP1_Hit'] and curr <= tp1_price:
                trade['TP1_Hit'] = True
                trade['Rem_Qty'] -= Config.TP1_QTY
                trade['SL'] = entry
            if not trade['TP2_Hit'] and curr <= tp2_price:
                trade['TP2_Hit'] = True
                trade['Rem_Qty'] -= Config.TP2_QTY
                trade['SL'] = tp1_price
            if trade['TP2_Hit']:
                trade['Peak_Price'] = min(trade['Peak_Price'], curr)
                dyn_sl = trade['Peak_Price'] * 1.005
                if dyn_sl < trade['SL']: trade['SL'] = dyn_sl

    def _close(self, trade, price, time, reason):
        trade['Exit_Price'] = price
        trade['Exit_Time'] = time
        trade['Exit_Reason'] = reason
        trade['status'] = 'CLOSED'
        trade['PnL_Pct'] = (price - trade['Entry_Price'])/trade['Entry_Price'] if trade['Side'] == 'LONG' else (trade['Entry_Price'] - price)/trade['Entry_Price']

if __name__ == "__main__":
    SniperOmegaV2().run()