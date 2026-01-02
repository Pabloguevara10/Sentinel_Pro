# =============================================================================
# NOMBRE: Ecosystem_Triad_Sim_4_2.py
# VERSIÓN: 4.2 (Agile Shield - Cobertura Rápida)
# DESCRIPCIÓN: 
#   - Basado en V4.1 (Smart Shield) que fue la más rentable (+202%).
#   - CAMBIO: Trigger de Cobertura reducido a -1.5% (antes -2.5%).
#   - OBJETIVO: Activar la defensa antes para reducir el drawdown flotante.
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
    from StructureScanner_2 import StructureScanner
    from Reporter import TradingReporter
    print("✅ Tríada Simulator V4.2 (Agile Shield): Librerías cargadas.")
except ImportError as e:
    print(f"❌ Error Crítico: {e}")
    sys.exit(1)

# =============================================================================
# 2. CONFIGURACIONES
# =============================================================================

class EcoConfig:
    """Configuración para Gamma (Sin Cambios)"""
    INITIAL_CAPITAL = 1000.0
    FILE_1D = "../data/historical/AAVEUSDT_1d.csv"
    FILE_4H = "../data/historical/AAVEUSDT_4h.csv"
    FILE_1H = "../data/historical/AAVEUSDT_1h.csv"
    FILE_15M = "../data/historical/AAVEUSDT_15m.csv"
    MAX_RISK_GAMMA = 2
    PCT_CAPITAL_PER_TRADE = 0.45 
    G_RSI_PERIOD = 14; G_FILTRO_DIST_FIBO_MAX = 0.008; G_FILTRO_MACD_MIN = 0.0
    G_HEDGE_DIST_FIBO_MIN = 0.012; G_HEDGE_MACD_MAX = -0.01
    G_TP_NORMAL = 0.035; G_SL_NORMAL = 0.020; G_TRAIL_NORM = 0.50
    G_TP_HEDGE = 0.045;  G_SL_HEDGE = 0.015;  G_TRAIL_HEDGE = 0.30

class ShadowConfig:
    """Configuración para ShadowHunter V4.2 (Agile Shield)"""
    INITIAL_CAPITAL = 1000.0
    BB_PERIOD = 20; BB_STD_DEV = 2.0
    MAX_SLOTS = 5
    MIN_SPACING_ATR = 1.0
    CASHFLOW_TARGET_PCT = 0.80
    SHADOW_TRAILING_PCT = 0.05
    
    # --- PARÁMETROS DE COBERTURA (HEDGING) ---
    # CAMBIO SOLICITADO: Trigger reducido a 1.5%
    HEDGE_TRIGGER_PNL = -0.015  # -1.5% activa el escudo (Más rápido)
    
    HEDGE_TRAILING_DEV = 0.015  # Mantenemos trailing del hedge en 1.5%
    
    # --- FILTROS ANTI-BUCLE (V4.1) ---
    HEDGE_COOLDOWN_CANDLES = 16  # 4 Horas de espera
    HEDGE_MIN_PRICE_GAP = 0.010  # 1.0% Gap

# =============================================================================
# 3. MOTORES LÓGICOS
# =============================================================================

# --- MOTOR 1: ECOSISTEMA (Gamma) ---
class EcosystemEngine:
    def __init__(self, df_1h, df_4h, df_1d):
        self.current_capital = EcoConfig.INITIAL_CAPITAL
        self.risk_manager = {'active_trades': []}
        self.reporter = TradingReporter("Ecosystem_Triad_Component", initial_capital=EcoConfig.INITIAL_CAPITAL)
        print(f"   🧠 [Eco] Motor Gamma Iniciado. Capital: ${self.current_capital:.2f}")
        self.scanner_1h = StructureScanner(df_1h); self.scanner_1h.precompute()
        self.df_1h = df_1h

    def get_dist(self, ts, scanner, df):
        idx = df.index.get_indexer([ts], method='pad')[0]
        if idx == -1: return 999
        ctx = scanner.get_fibonacci_context(idx)
        if not ctx: return 999
        price = df.iloc[idx]['close']
        return min([abs(price-l)/price for l in ctx['fibs'].values()])

    def process_candle(self, row_15m, i, full_df_15m):
        ts = row_15m.name
        for trade in list(self.risk_manager['active_trades']):
            self._manage_trade(trade, row_15m)
            if trade['status'] == 'CLOSED':
                pnl_usd = (trade['Exit_Price'] - trade['Entry_Price']) * trade['Rem_Qty']
                if trade['Side'] == 'SHORT': pnl_usd *= -1
                self.current_capital += pnl_usd
                trade['Capital_After'] = self.current_capital
                self.reporter.add_trade(trade)
                self.risk_manager['active_trades'].remove(trade)
        self._check_gamma(row_15m, ts)

    def _check_gamma(self, row, ts):
        dist_1h = self.get_dist(ts, self.scanner_1h, self.df_1h)
        macd = row['macd_hist']; rsi = row['rsi']
        signal = None; mode = None
        if rsi < 30 and dist_1h < EcoConfig.G_FILTRO_DIST_FIBO_MAX:
            signal = 'LONG'; mode = 'GAMMA_NORMAL'
        elif rsi > 70 and dist_1h < EcoConfig.G_FILTRO_DIST_FIBO_MAX:
            signal = 'SHORT'; mode = 'GAMMA_NORMAL'
        elif rsi < 25 and dist_1h > EcoConfig.G_HEDGE_DIST_FIBO_MIN and macd < EcoConfig.G_HEDGE_MACD_MAX:
            signal = 'SHORT'; mode = 'GAMMA_HEDGE'
        if signal: self._execute_entry(ts, row['close'], signal, mode, 'GAMMA')

    def _execute_entry(self, ts, price, side, mode, strat):
        curr_count = len(self.risk_manager['active_trades'])
        if curr_count >= EcoConfig.MAX_RISK_GAMMA: return
        allocated_usd = self.current_capital * EcoConfig.PCT_CAPITAL_PER_TRADE
        qty = allocated_usd / price
        trade = {
            'Trade_ID': f"ECO_{ts.strftime('%d%H%M')}",
            'Strategy': strat, 'Mode': mode, 'Side': side,
            'Entry_Time': ts, 'Entry_Price': price,
            'status': 'OPEN', 'Peak_Price': price, 'Rem_Qty': qty, 'Invested_USD': allocated_usd
        }
        sl_pct = EcoConfig.G_SL_NORMAL if 'NORMAL' in mode else EcoConfig.G_SL_HEDGE
        tp_pct = EcoConfig.G_TP_NORMAL
        trade['SL'] = price * (1 - sl_pct) if side == 'LONG' else price * (1 + sl_pct)
        trade['TP_Target'] = price * (1 + tp_pct) if side == 'LONG' else price * (1 - tp_pct)
        self.risk_manager['active_trades'].append(trade)

    def _manage_trade(self, trade, row):
        curr = row['close']
        if (trade['Side']=='LONG' and curr<=trade['SL']) or (trade['Side']=='SHORT' and curr>=trade['SL']):
            self._close(trade, curr, row.name, 'SL_HIT')
            return
        dist = abs(trade['Entry_Price'] - curr) / trade['Entry_Price']
        if dist > 0.015: 
            new_sl = curr * 0.995 if trade['Side']=='LONG' else curr * 1.005
            if trade['Side']=='LONG' and new_sl > trade['SL']: trade['SL'] = new_sl
            if trade['Side']=='SHORT' and new_sl < trade['SL']: trade['SL'] = new_sl

    def _close(self, trade, price, time, reason):
        trade['Exit_Price'] = price; trade['Exit_Time'] = time; trade['Exit_Reason'] = reason
        trade['status'] = 'CLOSED'
        trade['PnL_Pct'] = (price - trade['Entry_Price'])/trade['Entry_Price'] if trade['Side']=='LONG' else (trade['Entry_Price']-price)/trade['Entry_Price']

# --- MOTOR 2: SHADOW HUNTER V4.2 (Agile Shield) ---
class ShadowEngine:
    def __init__(self):
        self.current_capital = ShadowConfig.INITIAL_CAPITAL
        self.positions = {'LONG': [], 'SHORT': []}
        self.active_hedges = [] 
        self.reporter = TradingReporter("Shadow_Triad_Component", initial_capital=ShadowConfig.INITIAL_CAPITAL)
        print(f"   🛡️ [Shadow V4.2] Motor 'Agile Shield' Iniciado. Capital: ${self.current_capital:.2f}")

    def process_candle(self, row):
        price = row['close']
        atr = row['atr']
        
        # 1. Gestionar Hedges Activos
        for hedge in self.active_hedges[:]:
            self._manage_hedge(hedge, row)
            if hedge['status'] == 'CLOSED':
                self.active_hedges.remove(hedge)
        
        # 2. Gestionar Posiciones Principales
        for side in ['LONG', 'SHORT']:
            for pos in self.positions[side][:]:
                self._manage_main_pos(pos, row)
                if pos['qty_total'] <= 0.0001:
                    self.positions[side].remove(pos)
        
        # 3. Buscar Nuevas Entradas
        upper = row['bb_upper']; lower = row['bb_lower']
        
        if row['high'] >= upper and self._can_open('SHORT', price, atr):
            size_usd = self.current_capital / ShadowConfig.MAX_SLOTS
            qty = size_usd / price
            self._open_pos('SHORT', price, qty, row, size_usd)
            
        if row['low'] <= lower and self._can_open('LONG', price, atr):
            size_usd = self.current_capital / ShadowConfig.MAX_SLOTS
            qty = size_usd / price
            self._open_pos('LONG', price, qty, row, size_usd)

    def _manage_main_pos(self, pos, row):
        curr = row['close']
        entry = pos['entry_price']
        
        # PnL Actual
        pnl_pct = (curr - entry)/entry if pos['side']=='LONG' else (entry - curr)/entry
        if pnl_pct > pos['max_pnl']: pos['max_pnl'] = pnl_pct
        
        # --- TRIGGER DE COBERTURA (AGILE -1.5%) ---
        has_hedge = any(h['parent_id'] == pos['id'] for h in self.active_hedges)
        
        if pnl_pct < ShadowConfig.HEDGE_TRIGGER_PNL and not has_hedge:
            if self._is_hedge_allowed(pos, curr, row.name):
                self._activate_hedge(pos, curr, row.name)

        # Salida Normal
        bb_width = row['bb_width'] * row['bb_mid']
        target = entry + (bb_width * ShadowConfig.CASHFLOW_TARGET_PCT) if pos['side']=='LONG' else entry - (bb_width * ShadowConfig.CASHFLOW_TARGET_PCT)
        
        hit_tp = (pos['side']=='LONG' and row['high']>=target) or (pos['side']=='SHORT' and row['low']<=target)
        if hit_tp:
            self._close_main(pos, target, row.name, 'TARGET_HIT')
            return

        # Trailing Normal
        if pos['max_pnl'] > 0.01: 
            trigger = pos['max_pnl'] - ShadowConfig.SHADOW_TRAILING_PCT
            if pnl_pct < trigger and pnl_pct > 0:
                self._close_main(pos, curr, row.name, 'TRAILING_STOP')

    def _is_hedge_allowed(self, pos, curr_price, curr_time):
        last_time = pos.get('last_hedge_exit_time')
        if last_time:
            diff = (curr_time - last_time).total_seconds() / 900 
            if diff < ShadowConfig.HEDGE_COOLDOWN_CANDLES: return False
        
        last_price = pos.get('last_hedge_entry_price')
        if last_price:
            if pos['side'] == 'LONG': 
                dist = (last_price - curr_price) / last_price
                if dist < ShadowConfig.HEDGE_MIN_PRICE_GAP: return False
            else: 
                dist = (curr_price - last_price) / last_price
                if dist < ShadowConfig.HEDGE_MIN_PRICE_GAP: return False
        return True

    def _activate_hedge(self, parent_pos, price, time):
        hedge_side = 'SHORT' if parent_pos['side'] == 'LONG' else 'LONG'
        hedge = {
            'type': 'HEDGE', 'parent_id': parent_pos['id'],
            'side': hedge_side, 'entry_price': price,
            'qty': parent_pos['qty_total'], 
            'start_time': time, 'max_profit_pct': 0.0,
            'status': 'OPEN'
        }
        self.active_hedges.append(hedge)
        parent_pos['last_hedge_entry_price'] = price

    def _manage_hedge(self, hedge, row):
        curr = row['close']
        entry = hedge['entry_price']
        profit_pct = (entry - curr)/entry if hedge['side']=='SHORT' else (curr - entry)/entry
        
        if profit_pct > hedge['max_profit_pct']: hedge['max_profit_pct'] = profit_pct
            
        trailing_trigger = hedge['max_profit_pct'] - ShadowConfig.HEDGE_TRAILING_DEV
        
        should_close = False
        if hedge['max_profit_pct'] > 0.005: 
            if profit_pct < trailing_trigger: should_close = True
        elif profit_pct < -0.015: 
             should_close = True
             
        if should_close:
            self._close_hedge(hedge, curr, row.name)

    def _close_hedge(self, hedge, price, time):
        pnl_usd = (price - hedge['entry_price']) * hedge['qty']
        if hedge['side'] == 'SHORT': pnl_usd *= -1
        
        trade_record = {
            'Trade_ID': f"HEDGE_{hedge['parent_id'].split('_')[-1]}",
            'Strategy': 'SHADOW_HEDGE', 'Side': hedge['side'],
            'Entry_Time': hedge['start_time'], 'Entry_Price': hedge['entry_price'],
            'Exit_Time': time, 'Exit_Price': price, 'Exit_Reason': 'HEDGE_TRAILING',
            'PnL_Pct': (price - hedge['entry_price'])/hedge['entry_price'] if hedge['side']=='LONG' else (hedge['entry_price']-price)/hedge['entry_price'],
            'Rem_Qty': hedge['qty'], 'Capital_After': self.current_capital
        }
        self.reporter.add_trade(trade_record)
        
        parent = self._find_parent(hedge['parent_id'])
        if parent:
            cost_improvement = pnl_usd / parent['qty_total']
            if parent['side'] == 'LONG': parent['entry_price'] -= cost_improvement
            else: parent['entry_price'] += cost_improvement
            parent['max_pnl'] = -999 
            parent['last_hedge_exit_time'] = time

        hedge['status'] = 'CLOSED'

    def _find_parent(self, pid):
        for side in ['LONG', 'SHORT']:
            for pos in self.positions[side]:
                if pos['id'] == pid: return pos
        return None

    def _can_open(self, side, price, atr):
        actives = self.positions[side]
        if len(actives) >= ShadowConfig.MAX_SLOTS: return False
        if actives:
            last = actives[-1]['entry_price']
            if abs(price - last) < (atr * ShadowConfig.MIN_SPACING_ATR): return False
        return True

    def _open_pos(self, side, price, qty, row, invested_usd):
        pos = {
            'id': f"SHADOW_{side[0]}_{row.name.strftime('%d%H%M')}",
            'side': side, 'entry_price': price, 'entry_time': row.name,
            'qty_total': qty, 'max_pnl': 0.0,
            'invested_usd': invested_usd,
            'last_hedge_exit_time': None,
            'last_hedge_entry_price': None
        }
        self.positions[side].append(pos)

    def _close_main(self, pos, price, time, reason):
        for hedge in self.active_hedges:
            if hedge['parent_id'] == pos['id']:
                self._close_hedge(hedge, price, time)
        
        pnl_usd = (price - pos['entry_price']) * pos['qty_total']
        if pos['side'] == 'SHORT': pnl_usd *= -1
        
        self.current_capital += pnl_usd
        
        trade = {
            'Trade_ID': pos['id'], 'Strategy': 'SHADOW_V4', 'Side': pos['side'],
            'Entry_Time': pos['entry_time'], 'Entry_Price': pos['entry_price'],
            'Exit_Time': time, 'Exit_Price': price, 'Exit_Reason': reason,
            'PnL_Pct': (price - pos['entry_price'])/pos['entry_price'] if pos['side']=='LONG' else (pos['entry_price']-price)/pos['entry_price'],
            'Rem_Qty': pos['qty_total'],
            'Capital_After': self.current_capital
        }
        self.reporter.add_trade(trade)
        pos['qty_total'] = 0

# =============================================================================
# 4. ORQUESTADOR
# =============================================================================
class TriadOrchestrator:
    def __init__(self):
        print("\n🎹 INICIANDO SIMULACIÓN TRÍADA V4.2 (AGILE SHIELD)...")
        self.load_and_prepare_data()
        self.eco_engine = EcosystemEngine(self.df_1h, self.df_4h, self.df_1d)
        self.shadow_engine = ShadowEngine()

    def load_and_prepare_data(self):
        print("⏳ Cargando y Sincronizando Datos...")
        def load(f):
            p = os.path.join(os.path.dirname(__file__), f)
            df = pd.read_csv(p)
            df.columns = [c.lower().strip() for c in df.columns]
            if 'timestamp' in df.columns:
                if df['timestamp'].iloc[0] > 10000000000:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            return df.dropna()

        self.df_15m = load(EcoConfig.FILE_15M)
        self.df_1h = load(EcoConfig.FILE_1H)
        self.df_4h = load(EcoConfig.FILE_4H)
        self.df_1d = load(EcoConfig.FILE_1D)

        # Indicadores
        df = self.df_15m.copy()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        k = df['close'].ewm(span=12).mean(); d = df['close'].ewm(span=26).mean()
        df['macd_hist'] = (k-d) - (k-d).ewm(span=9).mean()
        
        sma = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std()
        df['bb_upper'] = sma + (std * 2); df['bb_lower'] = sma - (std * 2)
        df['bb_mid'] = sma; df['bb_width'] = df['bb_upper'] - df['bb_lower']
        
        tr1 = df['high'] - df['low']; tr2 = (df['high'] - df['close'].shift(1)).abs()
        tr3 = (df['low'] - df['close'].shift(1)).abs()
        df['atr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()
        
        self.df_15m = df.dropna()
        print(f"✅ Data Lista: {len(self.df_15m)} velas 15m sincronizadas.")

    def run_simulation(self):
        print("🚀 Ejecutando Loop Sincronizado (Agile Shield)...")
        for i in range(len(self.df_15m)):
            row = self.df_15m.iloc[i]
            self.shadow_engine.process_candle(row)
            self.eco_engine.process_candle(row, i, self.df_15m)

        print("\n" + "="*50)
        print("🏁 SIMULACIÓN V4.2 FINALIZADA - RESULTADOS")
        print("="*50)
        
        print(f"\n📘 REPORTE GAMMA (Capital Final: ${self.eco_engine.current_capital:,.2f}):")
        self.eco_engine.reporter.generate_report()
        
        print(f"\n🛡️ REPORTE SHADOW V4.2 (Capital Final: ${self.shadow_engine.current_capital:,.2f}):")
        self.shadow_engine.reporter.generate_report()

if __name__ == "__main__":
    triad = TriadOrchestrator()
    triad.run_simulation()