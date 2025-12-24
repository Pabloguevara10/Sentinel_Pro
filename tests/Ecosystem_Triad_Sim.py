# =============================================================================
# NOMBRE: Ecosystem_Triad_Sim.py
# DESCRIPCIÓN: 
#   Simulador de "La Tríada": TrendHunter vs SwingHunter vs ShadowHunter.
#   - Asignación de Capital Independiente ($1000 c/u).
#   - Ejecución Simultánea para detectar correlación y rendimiento.
# =============================================================================

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

# --- CONFIGURACIÓN Y RUTAS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

# Búsqueda inteligente del archivo de data
DATA_FILE = "AAVEUSDT_15m.csv"
POSSIBLE_PATHS = [
    DATA_FILE,
    os.path.join(project_root, 'data', 'historical', DATA_FILE),
    os.path.join('data', 'historical', DATA_FILE)
]

class TriadConfig:
    # Capital Virtual por Estrategia
    CAP_TREND = 1000.0
    CAP_SWING = 1000.0
    CAP_SHADOW = 1000.0
    
    # --- 1. TREND HUNTER (GAMMA) ---
    TH_EMA_FAST = 50
    TH_EMA_SLOW = 200
    TH_ATR_SL_MULT = 2.0
    TH_RISK = 100.0 # USD por trade
    
    # --- 2. SWING HUNTER (ALPHA) ---
    SW_RSI_LEN = 14
    SW_RSI_OB = 60 # Overbought (para shorts en tendencia bajista)
    SW_RSI_OS = 40 # Oversold (para longs en tendencia alcista)
    SW_TP_PCT = 0.03 # Take Profit 3%
    SW_SL_PCT = 0.02 # Stop Loss 2%
    SW_RISK = 100.0
    
    # --- 3. SHADOW HUNTER V2 (CASCADING) ---
    SH_BB_LEN = 20
    SH_BB_STD = 2.0
    SH_UNIT = 100.0 # Base unit (Entry = 2x unit)
    SH_MAX_SLOTS = 5
    SH_ATR_SPACING = 1.0

# --- LABORATORIO DE INDICADORES ---
class Lab:
    @staticmethod
    def prepare_data(df):
        # Trend Indicators
        df['ema_fast'] = df['close'].ewm(span=TriadConfig.TH_EMA_FAST).mean()
        df['ema_slow'] = df['close'].ewm(span=TriadConfig.TH_EMA_SLOW).mean()
        
        # Volatility
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        tr = pd.concat([high-low, (high-close).abs(), (low-close).abs()], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=14).mean()
        
        # Momentum (Swing)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Bollinger (Shadow)
        sma = df['close'].rolling(window=TriadConfig.SH_BB_LEN).mean()
        std = df['close'].rolling(window=TriadConfig.SH_BB_LEN).std()
        df['bb_upper'] = sma + (std * TriadConfig.SH_BB_STD)
        df['bb_lower'] = sma - (std * TriadConfig.SH_BB_STD)
        df['bb_mid'] = sma
        df['bb_width_val'] = df['bb_upper'] - df['bb_lower']
        
        return df

# --- MOTOR TRIÁDICO ---
class TriadEngine:
    def __init__(self):
        # State Containers
        self.trend_pos = None # Solo 1 posición a la vez
        self.swing_pos = []   # Lista de swings
        self.shadow_pos = {'LONG': [], 'SHORT': []} # Listas de Shadows
        
        self.history = []
        print(f"🔱 INICIANDO SIMULACIÓN DE LA TRÍADA")

    def load(self):
        print("⏳ Cargando datos...")
        target = None
        for p in POSSIBLE_PATHS:
            if os.path.exists(p):
                target = p
                break
        
        if not target:
            print("❌ Error: No encuentro AAVEUSDT_15m.csv")
            sys.exit(1)
            
        try:
            self.df = pd.read_csv(target)
            self.df['datetime'] = pd.to_datetime(self.df['timestamp'], unit='ms')
            self.df = Lab.prepare_data(self.df)
            self.df.dropna(inplace=True)
            self.df.reset_index(drop=True, inplace=True)
            print(f"✅ Data Lista: {len(self.df)} velas.")
        except Exception as e:
            print(f"❌ Error procesando data: {e}")
            sys.exit(1)

    def run(self):
        print("🚀 Ejecutando Motores...")
        for i, row in self.df.iterrows():
            self._engine_trend(row)
            self._engine_swing(row)
            self._engine_shadow(row)
            
        self._report()

    # ---------------------------------------------------------
    # MOTOR 1: TREND HUNTER (GAMMA)
    # ---------------------------------------------------------
    def _engine_trend(self, row):
        # Exit Logic
        if self.trend_pos:
            p = self.trend_pos
            # Trailing SL update
            if p['side'] == 'LONG':
                new_sl = row['close'] - (row['atr'] * TriadConfig.TH_ATR_SL_MULT)
                if new_sl > p['sl']: p['sl'] = new_sl
                if row['low'] <= p['sl']:
                    self._close(p, row, p['sl'], 'SL_TRAIL')
                    self.trend_pos = None
            else:
                new_sl = row['close'] + (row['atr'] * TriadConfig.TH_ATR_SL_MULT)
                if new_sl < p['sl']: p['sl'] = new_sl
                if row['high'] >= p['sl']:
                    self._close(p, row, p['sl'], 'SL_TRAIL')
                    self.trend_pos = None
        
        # Entry Logic
        if self.trend_pos is None:
            ema_fast = row['ema_fast']
            ema_slow = row['ema_slow']
            price = row['close']
            
            # Cross Over
            if ema_fast > ema_slow and price > ema_fast:
                self.trend_pos = {
                    'strat': 'TREND', 'side': 'LONG', 'entry': price,
                    'qty': TriadConfig.TH_RISK / price,
                    'sl': price - (row['atr'] * TriadConfig.TH_ATR_SL_MULT),
                    'time': row['datetime']
                }
            elif ema_fast < ema_slow and price < ema_fast:
                self.trend_pos = {
                    'strat': 'TREND', 'side': 'SHORT', 'entry': price,
                    'qty': TriadConfig.TH_RISK / price,
                    'sl': price + (row['atr'] * TriadConfig.TH_ATR_SL_MULT),
                    'time': row['datetime']
                }

    # ---------------------------------------------------------
    # MOTOR 2: SWING HUNTER (ALPHA)
    # ---------------------------------------------------------
    def _engine_swing(self, row):
        # Manage Exits
        for s in self.swing_pos[:]:
            exit_px = None
            reason = None
            if s['side'] == 'LONG':
                if row['high'] >= s['tp']: exit_px, reason = s['tp'], 'TP_HIT'
                elif row['low'] <= s['sl']: exit_px, reason = s['sl'], 'SL_HIT'
            else:
                if row['low'] <= s['tp']: exit_px, reason = s['tp'], 'TP_HIT'
                elif row['high'] >= s['sl']: exit_px, reason = s['sl'], 'SL_HIT'
            
            if exit_px:
                self._close(s, row, exit_px, reason)
                self.swing_pos.remove(s)

        # Entry Logic (Solo a favor de tendencia EMA)
        trend_bull = row['ema_fast'] > row['ema_slow']
        trend_bear = row['ema_fast'] < row['ema_slow']
        
        if trend_bull and row['rsi'] < TriadConfig.SW_RSI_OS:
            self._open_swing('LONG', row)
        elif trend_bear and row['rsi'] > TriadConfig.SW_RSI_OB:
            self._open_swing('SHORT', row)

    def _open_swing(self, side, row):
        if len(self.swing_pos) >= 3: return # Límite concurrencia
        price = row['close']
        self.swing_pos.append({
            'strat': 'SWING', 'side': side, 'entry': price,
            'qty': TriadConfig.SW_RISK / price,
            'tp': price * (1 + TriadConfig.SW_TP_PCT) if side=='LONG' else price * (1 - TriadConfig.SW_TP_PCT),
            'sl': price * (1 - TriadConfig.SW_SL_PCT) if side=='LONG' else price * (1 + TriadConfig.SW_SL_PCT),
            'time': row['datetime']
        })

    # ---------------------------------------------------------
    # MOTOR 3: SHADOW HUNTER V2 (CASCADING)
    # ---------------------------------------------------------
    def _engine_shadow(self, row):
        self._manage_shadow('LONG', row)
        self._manage_shadow('SHORT', row)
        
        price = row['close']
        atr = row['atr']
        
        # Entries
        if row['high'] >= row['bb_upper']:
            if self._can_shadow('SHORT', price, atr):
                self._open_shadow('SHORT', price, row)
            # Add-on Logic simplified
            for p in self.shadow_pos['SHORT']:
                if p['adds'] < 1 and price > p['entry']*1.01: self._add_shadow(p, price)

        if row['low'] <= row['bb_lower']:
            if self._can_shadow('LONG', price, atr):
                self._open_shadow('LONG', price, row)
            for p in self.shadow_pos['LONG']:
                if p['adds'] < 1 and price < p['entry']*0.99: self._add_shadow(p, price)

    def _can_shadow(self, side, price, atr):
        lst = self.shadow_pos[side]
        if len(lst) >= TriadConfig.SH_MAX_SLOTS: return False
        if len(lst) > 0:
            if abs(price - lst[-1]['entry']) < (atr * TriadConfig.SH_ATR_SPACING): return False
        return True

    def _open_shadow(self, side, price, row):
        qty = (TriadConfig.SH_UNIT * 2) / price
        self.shadow_pos[side].append({
            'strat': 'SHADOW', 'side': side, 'entry': price,
            'qty_tot': qty, 'qty_cf': qty/2,
            'cf_done': False, 'adds': 0, 'max_pnl': 0.0,
            'time': row['datetime']
        })

    def _add_shadow(self, p, price):
        # Promediar
        add_q = TriadConfig.SH_UNIT / price
        new_tot = p['qty_tot'] + add_q
        new_px = ((p['qty_tot']*p['entry']) + (add_q*price)) / new_tot
        p['entry'] = new_px
        p['qty_tot'] = new_tot
        p['adds'] += 1
        if not p['cf_done']: p['qty_cf'] = new_tot/2

    def _manage_shadow(self, side, row):
        for p in self.shadow_pos[side][:]:
            price = row['close']
            target_dist = row['bb_width_val'] * 0.8
            
            if side == 'LONG':
                pnl = (price - p['entry'])/p['entry']
                target = p['entry'] + target_dist
                hit_target = row['high'] >= target
            else:
                pnl = (p['entry'] - price)/p['entry']
                target = p['entry'] - target_dist
                hit_target = row['low'] <= target
            
            # Cashflow
            if not p['cf_done'] and hit_target:
                pnl_usd = (target - p['entry']) * p['qty_cf'] if side=='LONG' else (p['entry'] - target) * p['qty_cf']
                self.history.append({'Strategy': 'SHADOW', 'Side': side, 'PnL': pnl_usd, 'Time': row['datetime'], 'Reason': 'CASHFLOW'})
                p['qty_tot'] -= p['qty_cf']
                p['qty_cf'] = 0
                p['cf_done'] = True
                continue
            
            # Trailing Shadow
            if pnl > p['max_pnl']: p['max_pnl'] = pnl
            if p['max_pnl'] > 0.01:
                if pnl < (p['max_pnl'] - 0.05) and pnl > 0:
                    pnl_usd = (price - p['entry']) * p['qty_tot'] if side=='LONG' else (p['entry'] - price) * p['qty_tot']
                    self.history.append({'Strategy': 'SHADOW', 'Side': side, 'PnL': pnl_usd, 'Time': row['datetime'], 'Reason': 'SHADOW_TRAIL'})
                    self.shadow_pos[side].remove(p)

    # ---------------------------------------------------------
    # UTILS
    # ---------------------------------------------------------
    def _close(self, trade, row, price, reason):
        entry = trade['entry']
        qty = trade.get('qty', trade.get('qty_tot', 0))
        if trade['side'] == 'LONG':
            pnl = (price - entry) * qty
        else:
            pnl = (entry - price) * qty
        
        self.history.append({
            'Strategy': trade['strat'],
            'Side': trade['side'],
            'PnL': round(pnl, 2),
            'Time': row['datetime'],
            'Reason': reason
        })

    def _report(self):
        df = pd.DataFrame(self.history)
        if df.empty:
            print("⚠️ No trades.")
            return
            
        print("\n" + "="*50)
        print("📊 REPORTE DE LA TRÍADA (ECOSYSTEM TRIAD)")
        print("="*50)
        
        # Group by Strategy
        grouped = df.groupby('Strategy')['PnL'].agg(['count', 'sum', 'mean'])
        grouped['WinRate'] = df.groupby('Strategy')['PnL'].apply(lambda x: (x > 0).sum() / len(x) * 100)
        
        print(grouped)
        print("-" * 50)
        print(f"TOTAL PNL: ${df['PnL'].sum():.2f}")
        
        df.to_csv("Ecosystem_Triad_AUDIT.csv", index=False)
        print("\n✅ Archivo guardado: Ecosystem_Triad_AUDIT.csv")

if __name__ == "__main__":
    eng = TriadEngine()
    eng.load()
    eng.run()