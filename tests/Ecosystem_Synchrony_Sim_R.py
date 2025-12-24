# =============================================================================
# NOMBRE: Ecosystem_Synchrony_Sim.py
# DESCRIPCIÓN: 
#   Simulador de Ecosistema Unificado.
#   Ejecuta TrendHunter Gamma (V7) y SwingHunter Alpha (V3) simultáneamente.
#   Gestión de Riesgo Centralizada con Sistema de Cupos Dinámicos.
# =============================================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN COMPARTIDA ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
tools_path = os.path.join(project_root, 'tools')
sys.path.append(tools_path)

try:
    from StructureScanner import StructureScanner
    from Reporter import TradingReporter
    print("✅ Ecosistema: Herramientas cargadas.")
except ImportError:
    print("⚠️ Advertencia: Ejecutando sin herramientas externas (Mock Mode).")

class Config:
    # Rutas
    FILE_1D = "../data/historical/AAVEUSDT_1d.csv"
    FILE_4H = "../data/historical/AAVEUSDT_4h.csv"
    FILE_1H = "../data/historical/AAVEUSDT_1h.csv"
    FILE_15M = "../data/historical/AAVEUSDT_15m.csv"
    
    # --- LIMITES DE RIESGO ---
    MAX_RISK_GAMMA = 2
    MAX_RISK_SWING = 2
    MAX_RISK_TOTAL = 3
    
    # --- GAMMA V7 (SCALPING) CONFIG ---
    G_RSI_PERIOD = 14
    G_FILTRO_DIST_FIBO_MAX = 0.008
    G_FILTRO_MACD_MIN = 0.0
    G_HEDGE_DIST_FIBO_MIN = 0.012
    G_HEDGE_MACD_MAX = -0.01
    
    # Gamma Exits
    G_TP_NORMAL = 0.035; G_SL_NORMAL = 0.020; G_TRAIL_NORM = 0.50
    G_TP_HEDGE = 0.045;  G_SL_HEDGE = 0.015;  G_TRAIL_HEDGE = 0.30

    # --- SWING V3 (FRACTIONAL) CONFIG ---
    S_FILTRO_DIST_FIBO_MACRO = 0.025
    S_FILTRO_MACD_MIN = 0.0
    S_HEDGE_DIST_FIBO_MIN = 0.050
    S_HEDGE_MACD_MAX = -0.05
    
    # Swing Exits
    S_SL_INIT_NORM = 0.06; S_SL_INIT_HEDGE = 0.03
    S_TP1_DIST = 0.06; S_TP1_QTY = 0.30
    S_TP2_DIST = 0.12; S_TP2_QTY = 0.30
    S_RUNNER_TRAIL_START = 0.15; S_RUNNER_GAP = 0.03

# =============================================================================
# 2. MOTORES DE ESTRATEGIA (BRAINS)
# =============================================================================
class GammaBrainV7:
    def evaluate(self, row, context):
        """Retorna señal Gamma (Normal o Hedge)"""
        # Contexto
        macd = row['macd_hist']
        rsi = row['rsi']
        prev_rsi = context['prev_rsi']
        dist_fibo = context['dist_1h'] # Usamos 1H para estructura Gamma
        
        rsi_slope = rsi - prev_rsi
        
        signal = None
        mode = None
        
        # Intención
        long_intent = rsi < 30 and rsi_slope > 3
        short_intent = rsi > 70 and rsi_slope < -3
        
        if long_intent:
            # Normal
            if macd > Config.G_FILTRO_MACD_MIN and dist_fibo < Config.G_FILTRO_DIST_FIBO_MAX:
                signal = 'LONG'; mode = 'GAMMA_NORMAL'
            # Hedge
            elif macd < Config.G_HEDGE_MACD_MAX and dist_fibo > Config.G_HEDGE_DIST_FIBO_MIN:
                signal = 'SHORT'; mode = 'GAMMA_HEDGE'
                
        elif short_intent:
            if macd < -Config.G_FILTRO_MACD_MIN and dist_fibo < Config.G_FILTRO_DIST_FIBO_MAX:
                signal = 'SHORT'; mode = 'GAMMA_NORMAL'
            elif macd > -Config.G_HEDGE_MACD_MAX and dist_fibo > Config.G_HEDGE_DIST_FIBO_MIN:
                signal = 'LONG'; mode = 'GAMMA_HEDGE'
                
        return signal, mode

class SwingBrainV3:
    def evaluate(self, row_1h, context):
        """Retorna señal Swing (Normal o Hedge)"""
        macd = row_1h['macd_hist']
        rsi = row_1h['rsi']
        dist_macro = context['dist_macro'] # 1D/4H
        
        signal = None
        mode = None
        
        long_intent = rsi < 35
        short_intent = rsi > 65
        
        if long_intent:
            if macd > Config.S_FILTRO_MACD_MIN and dist_macro < Config.S_FILTRO_DIST_FIBO_MACRO:
                signal = 'LONG'; mode = 'SWING_NORMAL'
            elif macd < Config.S_HEDGE_MACD_MAX and dist_macro > Config.S_HEDGE_DIST_FIBO_MIN:
                signal = 'SHORT'; mode = 'SWING_HEDGE'
        
        elif short_intent:
            if macd < -Config.S_FILTRO_MACD_MIN and dist_macro < Config.S_FILTRO_DIST_FIBO_MACRO:
                signal = 'SHORT'; mode = 'SWING_NORMAL'
            elif macd > -Config.S_HEDGE_MACD_MAX and dist_macro > Config.S_HEDGE_DIST_FIBO_MIN:
                signal = 'LONG'; mode = 'SWING_HEDGE'
                
        return signal, mode

# =============================================================================
# 3. GESTOR DE RIESGO CENTRAL (EL JUEZ)
# =============================================================================
class RiskManager:
    def __init__(self):
        self.active_trades = []
        
    def check_slot(self, strategy_type):
        """
        Verifica si hay cupo. 
        Solo cuentan las operaciones que NO están en Break Even (Risk Trades).
        """
        risk_trades = [t for t in self.active_trades if not t['Is_Risk_Free']]
        
        total_risk = len(risk_trades)
        gamma_risk = len([t for t in risk_trades if 'GAMMA' in t['Mode']])
        swing_risk = len([t for t in risk_trades if 'SWING' in t['Mode']])
        
        if total_risk >= Config.MAX_RISK_TOTAL: return False
        
        if strategy_type == 'GAMMA':
            return gamma_risk < Config.MAX_RISK_GAMMA
        elif strategy_type == 'SWING':
            return swing_risk < Config.MAX_RISK_SWING
            
        return False

    def add_trade(self, trade):
        self.active_trades.append(trade)

    def update_risk_status(self, trade):
        """Si el SL ya está en precio de entrada o mejor, libera cupo."""
        if trade['Side'] == 'LONG':
            if trade['SL'] >= trade['Entry_Price']: trade['Is_Risk_Free'] = True
        else:
            if trade['SL'] <= trade['Entry_Price']: trade['Is_Risk_Free'] = True

# =============================================================================
# 4. SIMULADOR UNIFICADO
# =============================================================================
class EcosystemSimulator:
    def __init__(self):
        self.risk_manager = RiskManager()
        self.gamma_brain = GammaBrainV7()
        self.swing_brain = SwingBrainV3()
        self.reporter = TradingReporter("Ecosystem_Synchrony_V1", initial_capital=1000)
        
        print("\n🌐 INICIANDO ECOSISTEMA SINCRONIZADO...")
        self.load_data()
        
    def load_data(self):
        # Carga simplificada
        def load(f):
            p = os.path.join(os.path.dirname(__file__), f)
            if not os.path.exists(p): return pd.DataFrame()
            df = pd.read_csv(p)
            df.columns = [c.lower().strip() for c in df.columns]
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            return self._add_indicators(df)

        self.df_1d = load(Config.FILE_1D)
        self.df_4h = load(Config.FILE_4H)
        self.df_1h = load(Config.FILE_1H)
        self.df_15m = load(Config.FILE_15M)
        
        # Init Scanners
        self.scanners = {}
        if not self.df_1h.empty: self.scanners['1h'] = StructureScanner(self.df_1h)
        if not self.df_4h.empty: self.scanners['4h'] = StructureScanner(self.df_4h)
        if not self.df_1d.empty: self.scanners['1d'] = StructureScanner(self.df_1d)
        
        for s in self.scanners.values(): s.precompute()

    def _add_indicators(self, df):
        # RSI & MACD
        df['rsi'] = 100 - (100 / (1 + (df['close'].diff().where(df['close'].diff()>0,0).rolling(14).mean() / (-df['close'].diff().where(df['close'].diff()<0,0).rolling(14).mean()))))
        k = df['close'].ewm(span=12).mean()
        d = df['close'].ewm(span=26).mean()
        df['macd_hist'] = (k-d) - (k-d).ewm(span=9).mean()
        return df.dropna()

    def get_dist(self, ts, scanner, df):
        idx = df.index.get_indexer([ts], method='pad')[0]
        if idx == -1: return 999
        ctx = scanner.get_fibonacci_context(idx)
        if not ctx: return 999
        price = df.iloc[idx]['close']
        return min([abs(price-l)/price for l in ctx['fibs'].values()])

    def run(self):
        if self.df_15m.empty: return
        print(f"🚀 Ejecutando Loop Temporal (15m ticks)...")
        
        # Iterar sobre 15m (Reloj del Sistema)
        for i in range(50, len(self.df_15m)):
            row_15m = self.df_15m.iloc[i]
            ts = row_15m.name
            
            # --- 1. GESTIÓN DE POSICIONES ACTIVAS ---
            # (Trailing, TP, SL, Liberación de Cupo)
            for trade in list(self.risk_manager.active_trades):
                self._manage_trade(trade, row_15m) # Actualiza SL, TP hits
                self.risk_manager.update_risk_status(trade) # Revisa si es B/E
                
                if trade['status'] == 'CLOSED':
                    self.reporter.add_trade(trade)
                    self.risk_manager.active_trades.remove(trade)

            # --- 2. GATILLO SWING (Solo al inicio de cada hora) ---
            if ts.minute == 0 and self.risk_manager.check_slot('SWING'):
                # Buscar datos de 1H correspondientes (Lookback seguro)
                idx_1h = self.df_1h.index.get_indexer([ts], method='pad')[0]
                if idx_1h != -1:
                    row_1h = self.df_1h.iloc[idx_1h]
                    # Contexto Macro (1D/4H)
                    d1 = self.get_dist(ts, self.scanners.get('1d'), self.df_1d)
                    d4 = self.get_dist(ts, self.scanners.get('4h'), self.df_4h)
                    
                    ctx = {'dist_macro': min(d1, d4)}
                    sig, mode = self.swing_brain.evaluate(row_1h, ctx)
                    
                    if sig:
                        self._execute_entry(ts, row_1h['close'], sig, mode, 'SWING')

            # --- 3. GATILLO GAMMA (Cada 15m) ---
            if self.risk_manager.check_slot('GAMMA'):
                d1h = self.get_dist(ts, self.scanners.get('1h'), self.df_1h)
                ctx = {'prev_rsi': self.df_15m.iloc[i-1]['rsi'], 'dist_1h': d1h}
                sig, mode = self.gamma_brain.evaluate(row_15m, ctx)
                
                if sig:
                    self._execute_entry(ts, row_15m['close'], sig, mode, 'GAMMA')

        self.reporter.generate_report()

    def _execute_entry(self, ts, price, side, mode, strat_type):
        entry = price
        trade = {
            'Trade_ID': f"{strat_type[0]}_{ts.strftime('%d%H%M')}",
            'Strategy': strat_type,
            'Mode': mode,
            'Side': side,
            'Entry_Time': ts, 'Entry_Price': entry,
            'status': 'OPEN',
            'Is_Risk_Free': False,
            'Peak_Price': entry,
            'Rem_Qty': 1.0,
            'TP1_Hit': False, 'TP2_Hit': False
        }
        
        # Configurar SL/TP Inicial
        if strat_type == 'GAMMA':
            sl_pct = Config.G_SL_NORMAL if 'NORMAL' in mode else Config.G_SL_HEDGE
            tp_ref = Config.G_TP_NORMAL if 'NORMAL' in mode else Config.G_TP_HEDGE
        else: # SWING
            sl_pct = Config.S_SL_INIT_NORM if 'NORMAL' in mode else Config.S_SL_INIT_HEDGE
            tp_ref = Config.S_TP2_DIST # Referencia
            
        trade['SL'] = entry * (1 - sl_pct) if side == 'LONG' else entry * (1 + sl_pct)
        trade['Fibo_Target'] = entry * (1 + tp_ref) if side == 'LONG' else entry * (1 - tp_ref)
        
        self.risk_manager.add_trade(trade)

    def _manage_trade(self, trade, row):
        # Lógica Unificada de Gestión (Simplificada para simulación)
        curr = row['close']
        entry = trade['Entry_Price']
        side = trade['Side']
        strat = trade['Strategy']
        mode = trade['Mode']
        
        # Actualizar Pico
        if side == 'LONG': trade['Peak_Price'] = max(trade['Peak_Price'], curr)
        else: trade['Peak_Price'] = min(trade['Peak_Price'], curr)
        
        # CHECK SL
        hit_sl = (side == 'LONG' and curr <= trade['SL']) or (side == 'SHORT' and curr >= trade['SL'])
        if hit_sl:
            self._close(trade, curr, row.name, 'SL_HIT')
            return

        # GESTIÓN ESPECÍFICA
        if strat == 'GAMMA':
            self._manage_gamma(trade, curr, entry, side, mode)
        else:
            self._manage_swing(trade, curr, entry, side, mode)

    def _manage_gamma(self, trade, curr, entry, side, mode):
        # Trailing Simple
        trigger = Config.G_TRAIL_NORM if 'NORMAL' in mode else Config.G_TRAIL_HEDGE
        target_dist = abs(trade['Fibo_Target'] - entry)
        prof_dist = abs(curr - entry)
        pct_prof = prof_dist / target_dist if target_dist > 0 else 0
        
        if pct_prof >= 1.0: # TP Hit
            self._close(trade, curr, trade['Entry_Time'], 'TP_FULL') # Mock time
        elif pct_prof >= trigger:
            # Activar Trailing
            gap = entry * 0.005 # 0.5% gap
            if side == 'LONG':
                new_sl = curr - gap
                if new_sl > trade['SL']: trade['SL'] = new_sl
            else:
                new_sl = curr + gap
                if new_sl < trade['SL']: trade['SL'] = new_sl

    def _manage_swing(self, trade, curr, entry, side, mode):
        # Gestión Fraccionada V3
        if 'NORMAL' not in mode: return # Hedge Swing es simple (ver lógica previa)
        
        gain = (curr - entry)/entry if side == 'LONG' else (entry - curr)/entry
        
        # TP1 (6%) -> BE
        if not trade['TP1_Hit'] and gain >= Config.S_TP1_DIST:
            trade['TP1_Hit'] = True
            trade['Rem_Qty'] -= Config.S_TP1_QTY
            trade['SL'] = entry # BE Activado -> Libera Cupo
            
        # TP2 (12%)
        if not trade['TP2_Hit'] and gain >= Config.S_TP2_DIST:
            trade['TP2_Hit'] = True
            trade['Rem_Qty'] -= Config.S_TP2_QTY
            trade['SL'] = entry * (1 + Config.S_TP1_DIST) if side=='LONG' else entry * (1 - Config.S_TP1_DIST)

    def _close(self, trade, price, time, reason):
        trade['Exit_Price'] = price
        trade['Exit_Time'] = time
        trade['Exit_Reason'] = reason
        trade['status'] = 'CLOSED'
        # Calc PnL simple
        trade['PnL_Pct'] = (price - trade['Entry_Price'])/trade['Entry_Price'] if trade['Side'] == 'LONG' else (trade['Entry_Price'] - price)/trade['Entry_Price']

if __name__ == "__main__":
    EcosystemSimulator().run()