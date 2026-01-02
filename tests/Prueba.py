# =============================================================================
# NOMBRE: Ecosystem_Triad_Sim_4_6.py
# VERSIÓN: 4.6 (Strict S/L 2% + 3-Stage Exit)
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
    print("✅ Tríada Simulator V4.6: Librerías cargadas.")
except ImportError:
    print("⚠️ Librerías externas no encontradas. Usando MOCKS.")
    class StructureScanner:
        def __init__(self, df): pass
        def precompute(self): pass
        def get_fibonacci_context(self, idx): 
            return {'fibs': {'0.236': 0, '0.382': 0, '0.5': 0, '0.618': 0, '0.786': 0}}
    class TradingReporter:
        def __init__(self, name, initial_capital): 
            self.trades = []
            self.initial_capital = initial_capital
        def add_trade(self, trade): self.trades.append(trade)
        def generate_report(self): 
            print(f"   📊 Reporte {self.initial_capital}: {len(self.trades)} operaciones cerradas.")
            if len(self.trades) > 0:
                df = pd.DataFrame(self.trades)
                pnl = df['PnL_Pct'].sum() * 100
                print(f"   💰 PnL Acumulado (s/ apalancamiento): {pnl:.2f}%")

# =============================================================================
# 2. CONFIGURACIONES
# =============================================================================

class EcoConfig:
    """Configuración Gamma V4.6"""
    INITIAL_CAPITAL = 1000.0
    
    FILE_1D = "../data/historical/AAVEUSDT_1d.csv"
    FILE_4H = "../data/historical/AAVEUSDT_4h.csv"
    FILE_1H = "../data/historical/AAVEUSDT_1h.csv"
    FILE_15M = "../data/historical/AAVEUSDT_15m.csv"
    
    MAX_RISK_GAMMA = 2
    PCT_CAPITAL_PER_TRADE = 0.15  
    LEVERAGE = 10                 
    
    G_RSI_PERIOD = 14
    G_FILTRO_DIST_FIBO_MAX = 0.008
    G_FILTRO_MACD_MIN = 0.0
    G_HEDGE_DIST_FIBO_MIN = 0.012
    G_HEDGE_MACD_MAX = -0.01
    
    # --- AJUSTE SOLICITADO V4.6 ---
    G_SL_NORMAL = 0.020   # CAMBIO: S/L vuelto a 2.0%
    G_SL_HEDGE = 0.015    # Ajuste proporcional (sniper)
    
    # Estructura de Salida (Mantenida de V4.5)
    G_TP_1 = 0.035        # TP1 3.5%
    G_TP_1_QTY = 0.50     # Vende 40%
    
    G_TP_2 = 0.045        # TP2 4.5%
    G_TP_2_QTY = 0.20     # Vende 30%
    
    # Trailing y BE
    G_BE_ACTIVATION = 0.015  
    G_BE_PROFIT = 0.005      
    G_TRAILING_DIST = 0.01   # Trailing a 1%

class ShadowConfig:
    """Configuración Shadow V4.2 (Sin cambios)"""
    INITIAL_CAPITAL = 1000.0
    BB_PERIOD = 20; BB_STD_DEV = 2.0
    MAX_SLOTS = 5
    MIN_SPACING_ATR = 1.0
    CASHFLOW_TARGET_PCT = 0.80
    SHADOW_TRAILING_PCT = 0.05
    HEDGE_TRIGGER_PNL = -0.015
    HEDGE_TRAILING_DEV = 0.015
    HEDGE_COOLDOWN_CANDLES = 16
    HEDGE_MIN_PRICE_GAP = 0.010

# =============================================================================
# 3. MOTORES LÓGICOS
# =============================================================================

class EcosystemEngine:
    def __init__(self, df_1h, df_4h, df_1d):
        self.current_capital = EcoConfig.INITIAL_CAPITAL
        self.risk_manager = {'active_trades': []}
        self.reporter = TradingReporter("Ecosystem_Triad_Component", initial_capital=EcoConfig.INITIAL_CAPITAL)
        print(f"   🧠 [Eco] Motor Gamma V4.6 (S/L 2% | TP1 40% | TP2 30% | Runner 30%).")
        
        try:
            self.scanner_1h = StructureScanner(df_1h)
            self.scanner_1h.precompute()
        except:
            self.scanner_1h = None 
        self.df_1h = df_1h

    def get_dist(self, ts, scanner, df):
        if scanner is None: return 0.005 
        try:
            idx = df.index.get_indexer([ts], method='pad')[0]
            if idx == -1: return 999
            ctx = scanner.get_fibonacci_context(idx)
            if not ctx: return 999
            price = df.iloc[idx]['close']
            if price == 0: return 999
            return min([abs(price-l)/price for l in ctx['fibs'].values()])
        except:
            return 999

    def process_candle(self, row_15m, i, full_df_15m):
        ts = row_15m.name
        for trade in list(self.risk_manager['active_trades']):
            self._manage_trade(trade, row_15m, i, full_df_15m)
            if trade['status'] == 'CLOSED':
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
        
        margin_usd = self.current_capital * EcoConfig.PCT_CAPITAL_PER_TRADE
        position_size_usd = margin_usd * EcoConfig.LEVERAGE
        qty = position_size_usd / price
        
        trade = {
            'Trade_ID': f"ECO_{ts.strftime('%d%H%M')}",
            'Strategy': strat, 'Mode': mode, 'Side': side,
            'Entry_Time': ts, 'Entry_Price': price,
            'status': 'OPEN', 
            'Rem_Qty': qty, 'Initial_Qty': qty,
            'Margin_USD': margin_usd, 'Invested_USD': position_size_usd,
            'tp1_hit': False,
            'tp2_hit': False, 
            'Max_Adverse_Price': price, 
            'Max_Favorable_Price': price
        }
        
        sl_pct = EcoConfig.G_SL_NORMAL if 'NORMAL' in mode else EcoConfig.G_SL_HEDGE
        
        if side == 'LONG':
            trade['SL'] = price * (1 - sl_pct)
            trade['TP1_Price'] = price * (1 + EcoConfig.G_TP_1)
            trade['TP2_Price'] = price * (1 + EcoConfig.G_TP_2)
        else:
            trade['SL'] = price * (1 + sl_pct)
            trade['TP1_Price'] = price * (1 - EcoConfig.G_TP_1)
            trade['TP2_Price'] = price * (1 - EcoConfig.G_TP_2)
            
        self.risk_manager['active_trades'].append(trade)

    def _manage_trade(self, trade, row, current_idx, full_df):
        curr = row['close']
        ts = row.name
        
        # Métricas DD
        if trade['Side'] == 'LONG':
            if curr < trade['Max_Adverse_Price']: trade['Max_Adverse_Price'] = curr
            if curr > trade['Max_Favorable_Price']: trade['Max_Favorable_Price'] = curr
        else:
            if curr > trade['Max_Adverse_Price']: trade['Max_Adverse_Price'] = curr
            if curr < trade['Max_Favorable_Price']: trade['Max_Favorable_Price'] = curr

        # 1. STOP LOSS (Cierra todo lo que quede)
        if (trade['Side']=='LONG' and curr<=trade['SL']) or (trade['Side']=='SHORT' and curr>=trade['SL']):
            self._analyze_post_mortem(trade, current_idx, full_df)
            self._close_partial(trade, trade['Rem_Qty'], curr, ts, 'SL_HIT')
            return

        # 2. TAKE PROFIT 1 (3.5% - Vende 40%)
        if not trade['tp1_hit']:
            tp1_triggered = (trade['Side']=='LONG' and curr >= trade['TP1_Price']) or \
                            (trade['Side']=='SHORT' and curr <= trade['TP1_Price'])
            if tp1_triggered:
                qty_to_close = trade['Initial_Qty'] * EcoConfig.G_TP_1_QTY
                qty_to_close = min(qty_to_close, trade['Rem_Qty'])
                
                self._close_partial(trade, qty_to_close, curr, ts, 'TP1_HIT')
                trade['tp1_hit'] = True
                
                # Activa Trailing a 1%
                if trade['Side'] == 'LONG':
                    trade['SL'] = curr * (1 - EcoConfig.G_TRAILING_DIST)
                else:
                    trade['SL'] = curr * (1 + EcoConfig.G_TRAILING_DIST)
                return 

        # 3. TAKE PROFIT 2 (4.5% - Vende 30%)
        if not trade['tp2_hit']:
            tp2_triggered = (trade['Side']=='LONG' and curr >= trade['TP2_Price']) or \
                            (trade['Side']=='SHORT' and curr <= trade['TP2_Price'])
            
            if tp2_triggered:
                qty_to_close = trade['Initial_Qty'] * EcoConfig.G_TP_2_QTY
                qty_to_close = min(qty_to_close, trade['Rem_Qty'])
                
                self._close_partial(trade, qty_to_close, curr, ts, 'TP2_HIT')
                trade['tp2_hit'] = True

        # 4. GESTIÓN DE TRAILING
        profit_pct = (curr - trade['Entry_Price'])/trade['Entry_Price'] if trade['Side']=='LONG' else (trade['Entry_Price']-curr)/trade['Entry_Price']
        
        # BE Avanzado (Antes de TP1)
        if not trade['tp1_hit']:
            if profit_pct >= EcoConfig.G_BE_ACTIVATION:
                be_price = trade['Entry_Price'] * (1 + EcoConfig.G_BE_PROFIT) if trade['Side']=='LONG' else trade['Entry_Price'] * (1 - EcoConfig.G_BE_PROFIT)
                if trade['Side'] == 'LONG' and be_price > trade['SL']: trade['SL'] = be_price
                elif trade['Side'] == 'SHORT' and be_price < trade['SL']: trade['SL'] = be_price
        
        # Trailing Stop General (Activo tras TP1)
        if trade['tp1_hit']:
            if trade['Side'] == 'LONG':
                new_sl = curr * (1 - EcoConfig.G_TRAILING_DIST)
                if new_sl > trade['SL']: trade['SL'] = new_sl
            else:
                new_sl = curr * (1 + EcoConfig.G_TRAILING_DIST)
                if new_sl < trade['SL']: trade['SL'] = new_sl

    def _analyze_post_mortem(self, trade, idx, df):
        look_ahead = 96
        max_idx = len(df) - 1
        end_idx = min(idx + look_ahead, max_idx)
        future_data = df.iloc[idx+1 : end_idx]
        
        recovered = False; hit_tp1 = False
        if trade['Side'] == 'LONG':
            if not future_data.empty:
                recovered = future_data['high'].max() >= trade['Entry_Price']
                hit_tp1 = future_data['high'].max() >= trade['TP1_Price']
        else:
            if not future_data.empty:
                recovered = future_data['low'].min() <= trade['Entry_Price']
                hit_tp1 = future_data['low'].min() <= trade['TP1_Price']
                
        trade['Post_SL_Recovery'] = recovered
        trade['Post_SL_TP1_Hit'] = hit_tp1

    def _close_partial(self, trade, qty, price, time, reason):
        if qty <= 0: return
        pnl_usd = (price - trade['Entry_Price']) * qty
        if trade['Side'] == 'SHORT': pnl_usd *= -1
        
        self.current_capital += pnl_usd
        
        if trade['Side'] == 'LONG':
            max_dd_pct = (trade['Max_Adverse_Price'] - trade['Entry_Price']) / trade['Entry_Price']
        else:
            max_dd_pct = (trade['Entry_Price'] - trade['Max_Adverse_Price']) / trade['Entry_Price']
            
        sub_trade = trade.copy()
        sub_trade['Exit_Price'] = price; sub_trade['Exit_Time'] = time; sub_trade['Exit_Reason'] = reason
        sub_trade['PnL_Pct'] = (price - trade['Entry_Price'])/trade['Entry_Price'] if trade['Side']=='LONG' else (trade['Entry_Price']-price)/trade['Entry_Price']
        sub_trade['Rem_Qty'] = 0; sub_trade['Closed_Qty'] = qty; sub_trade['Capital_After'] = self.current_capital
        sub_trade['Max_DD_During_Trade'] = max_dd_pct
        if 'Post_SL_Recovery' not in trade:
            sub_trade['Post_SL_Recovery'] = None; sub_trade['Post_SL_TP1_Hit'] = None
        
        self.reporter.add_trade(sub_trade)
        
        trade['Rem_Qty'] -= qty
        if trade['Rem_Qty'] <= 0.0001: trade['status'] = 'CLOSED'

class ShadowEngine:
    def __init__(self):
        self.current_capital = ShadowConfig.INITIAL_CAPITAL
        self.positions = {'LONG': [], 'SHORT': []}
        self.active_hedges = [] 
        self.reporter = TradingReporter("Shadow_Triad_Component", initial_capital=ShadowConfig.INITIAL_CAPITAL)
        print(f"   🛡️ [Shadow V4.2] Motor Iniciado. Capital: ${self.current_capital:.2f}")

    def process_candle(self, row):
        price = row['close']; atr = row['atr']
        for hedge in self.active_hedges[:]:
            self._manage_hedge(hedge, row)
            if hedge['status'] == 'CLOSED': self.active_hedges.remove(hedge)
        for side in ['LONG', 'SHORT']:
            for pos in self.positions[side][:]:
                self._manage_main_pos(pos, row)
                if pos['qty_total'] <= 0.0001: self.positions[side].remove(pos)
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
        curr = row['close']; entry = pos['entry_price']
        pnl_pct = (curr - entry)/entry if pos['side']=='LONG' else (entry - curr)/entry
        if pnl_pct > pos['max_pnl']: pos['max_pnl'] = pnl_pct
        has_hedge = any(h['parent_id'] == pos['id'] for h in self.active_hedges)
        if pnl_pct < ShadowConfig.HEDGE_TRIGGER_PNL and not has_hedge:
            if self._is_hedge_allowed(pos, curr, row.name): self._activate_hedge(pos, curr, row.name)
        bb_width = row['bb_width'] * row['bb_mid']
        target = entry + (bb_width * ShadowConfig.CASHFLOW_TARGET_PCT) if pos['side']=='LONG' else entry - (bb_width * ShadowConfig.CASHFLOW_TARGET_PCT)
        if (pos['side']=='LONG' and row['high']>=target) or (pos['side']=='SHORT' and row['low']<=target):
            self._close_main(pos, target, row.name, 'TARGET_HIT'); return
        if pos['max_pnl'] > 0.01: 
            trigger = pos['max_pnl'] - ShadowConfig.SHADOW_TRAILING_PCT
            if pnl_pct < trigger and pnl_pct > 0: self._close_main(pos, curr, row.name, 'TRAILING_STOP')

    def _is_hedge_allowed(self, pos, curr_price, curr_time):
        last_time = pos.get('last_hedge_exit_time')
        if last_time:
            if (curr_time - last_time).total_seconds() / 900 < ShadowConfig.HEDGE_COOLDOWN_CANDLES: return False
        last_price = pos.get('last_hedge_entry_price')
        if last_price:
            dist = (last_price - curr_price)/last_price if pos['side']=='LONG' else (curr_price - last_price)/last_price
            if dist < ShadowConfig.HEDGE_MIN_PRICE_GAP: return False
        return True

    def _activate_hedge(self, parent_pos, price, time):
        hedge_side = 'SHORT' if parent_pos['side'] == 'LONG' else 'LONG'
        hedge = {'type': 'HEDGE', 'parent_id': parent_pos['id'], 'side': hedge_side, 'entry_price': price,
                 'qty': parent_pos['qty_total'], 'start_time': time, 'max_profit_pct': 0.0, 'status': 'OPEN'}
        self.active_hedges.append(hedge)
        parent_pos['last_hedge_entry_price'] = price

    def _manage_hedge(self, hedge, row):
        curr = row['close']; entry = hedge['entry_price']
        profit_pct = (entry - curr)/entry if hedge['side']=='SHORT' else (curr - entry)/entry
        if profit_pct > hedge['max_profit_pct']: hedge['max_profit_pct'] = profit_pct
        trailing_trigger = hedge['max_profit_pct'] - ShadowConfig.HEDGE_TRAILING_DEV
        should_close = False
        if hedge['max_profit_pct'] > 0.005: 
            if profit_pct < trailing_trigger: should_close = True
        elif profit_pct < -0.015: should_close = True
        if should_close: self._close_hedge(hedge, curr, row.name)

    def _close_hedge(self, hedge, price, time):
        pnl_usd = (price - hedge['entry_price']) * hedge['qty']
        if hedge['side'] == 'SHORT': pnl_usd *= -1
        trade = {'Trade_ID': f"HEDGE_{hedge['parent_id'].split('_')[-1]}", 'Strategy': 'SHADOW_HEDGE', 'Side': hedge['side'],
                 'Entry_Time': hedge['start_time'], 'Exit_Time': time, 'PnL_Pct': 0, 'Rem_Qty': hedge['qty'], 'Capital_After': self.current_capital}
        self.reporter.add_trade(trade)
        parent = self._find_parent(hedge['parent_id'])
        if parent:
            cost_improvement = pnl_usd / parent['qty_total']
            if parent['side'] == 'LONG': parent['entry_price'] -= cost_improvement
            else: parent['entry_price'] += cost_improvement
            parent['max_pnl'] = -999; parent['last_hedge_exit_time'] = time
        hedge['status'] = 'CLOSED'

    def _find_parent(self, pid):
        for side in ['LONG', 'SHORT']:
            for p in self.positions[side]: 
                if p['id'] == pid: return p
        return None

    def _can_open(self, side, price, atr):
        actives = self.positions[side]
        if len(actives) >= ShadowConfig.MAX_SLOTS: return False
        if actives and abs(price - actives[-1]['entry_price']) < (atr * ShadowConfig.MIN_SPACING_ATR): return False
        return True

    def _open_pos(self, side, price, qty, row, invested_usd):
        pos = {'id': f"SHADOW_{side[0]}_{row.name.strftime('%d%H%M')}", 'side': side, 'entry_price': price, 'entry_time': row.name,
               'qty_total': qty, 'max_pnl': 0.0, 'invested_usd': invested_usd, 'last_hedge_exit_time': None, 'last_hedge_entry_price': None}
        self.positions[side].append(pos)

    def _close_main(self, pos, price, time, reason):
        for h in self.active_hedges:
            if h['parent_id'] == pos['id']: self._close_hedge(h, price, time)
        pnl_usd = (price - pos['entry_price']) * pos['qty_total']
        if pos['side'] == 'SHORT': pnl_usd *= -1
        self.current_capital += pnl_usd
        trade = {'Trade_ID': pos['id'], 'Strategy': 'SHADOW_V4', 'Side': pos['side'], 'Entry_Time': pos['entry_time'], 'Exit_Time': time,
                 'PnL_Pct': (price - pos['entry_price'])/pos['entry_price'] if pos['side']=='LONG' else (pos['entry_price']-price)/pos['entry_price'],
                 'Rem_Qty': pos['qty_total'], 'Capital_After': self.current_capital}
        self.reporter.add_trade(trade)
        pos['qty_total'] = 0

class TriadOrchestrator:
    def __init__(self):
        print("\n🎹 INICIANDO SIMULACIÓN TRÍADA V4.6 (STRICT SL 2%)...")
        self.load_and_prepare_data()
        self.eco_engine = EcosystemEngine(self.df_1h, self.df_4h, self.df_1d)
        self.shadow_engine = ShadowEngine()

    def load_and_prepare_data(self):
        print("⏳ Cargando y Sincronizando Datos...")
        def load(f):
            base_path = os.path.dirname(os.path.abspath(__file__))
            p = os.path.normpath(os.path.join(base_path, f))
            if not os.path.exists(p):
                print(f"   ⚠️ Fallback Data Dummy: {f}")
                dates = pd.date_range(end=datetime.now(), periods=1000, freq='15min')
                close = [100.0]
                for _ in range(len(dates)-1): close.append(close[-1] * (1 + np.random.uniform(-0.01, 0.01)))
                df = pd.DataFrame({'timestamp': dates, 'open': close, 'high': [c*1.005 for c in close], 
                                   'low': [c*0.995 for c in close], 'close': close, 'volume': 1000})
                df.set_index('timestamp', inplace=True)
                return df
            df = pd.read_csv(p)
            df.columns = [c.lower().strip() for c in df.columns]
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            return df.dropna()

        self.df_15m = load(EcoConfig.FILE_15M)
        self.df_1h = load(EcoConfig.FILE_1H)
        self.df_4h = load(EcoConfig.FILE_4H)
        self.df_1d = load(EcoConfig.FILE_1D)

        df = self.df_15m.copy()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 0.0001))))
        k = df['close'].ewm(span=12).mean(); d = df['close'].ewm(span=26).mean()
        df['macd_hist'] = (k-d) - (k-d).ewm(span=9).mean()
        sma = df['close'].rolling(20).mean(); std = df['close'].rolling(20).std()
        df['bb_upper'] = sma + (std*2); df['bb_lower'] = sma - (std*2)
        df['bb_mid'] = sma; df['bb_width'] = df['bb_upper'] - df['bb_lower']
        tr1 = df['high'] - df['low']; tr2 = (df['high'] - df['close'].shift(1)).abs(); tr3 = (df['low'] - df['close'].shift(1)).abs()
        df['atr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()
        self.df_15m = df.dropna()
        print(f"✅ Data Lista: {len(self.df_15m)} velas 15m sincronizadas.")

    def run_simulation(self):
        print("🚀 Ejecutando Loop Sincronizado...")
        if len(self.df_15m) == 0: return
        for i in range(len(self.df_15m)):
            row = self.df_15m.iloc[i]
            self.shadow_engine.process_candle(row)
            self.eco_engine.process_candle(row, i, self.df_15m)
        print("\n" + "="*50)
        print("🏁 SIMULACIÓN FINALIZADA - RESULTADOS")
        print("="*50)
        print(f"\n📘 REPORTE GAMMA (Capital Final: ${self.eco_engine.current_capital:,.2f}):")
        self.eco_engine.reporter.generate_report()
        print(f"\n🛡️ REPORTE SHADOW V4.2 (Capital Final: ${self.shadow_engine.current_capital:,.2f}):")
        self.shadow_engine.reporter.generate_report()

if __name__ == "__main__":
    triad = TriadOrchestrator()
    triad.run_simulation()