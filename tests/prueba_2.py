# =============================================================================
# NOMBRE: Ecosystem_Triad_Sim_5_3.py
# VERSIÓN: 5.3 (Path Debugger + Capital Cap)
# DESCRIPCIÓN: 
#   - Soluciona rutas relativas imprimiendo la ubicación exacta de búsqueda.
#   - Limita el Interés Compuesto para dar resultados realistas ($).
# =============================================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# --- 1. FIJAR SEMILLA (Para que los resultados sean repetibles si falla la data) ---
np.random.seed(42)

# --- 2. CONFIGURACIÓN DE ENTORNO ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
tools_path = os.path.join(project_root, 'tools')
sys.path.append(tools_path)

try:
    from StructureScanner_2 import StructureScanner
    from Reporter import TradingReporter
    print("✅ Librerías cargadas correctamente.")
except ImportError:
    print("⚠️ Usando Mocks internos (Librerías no encontradas).")
    class StructureScanner:
        def __init__(self, df): pass
        def precompute(self): pass
        def get_fibonacci_context(self, idx): return {'fibs': {'0.236': 0}}
    class TradingReporter:
        def __init__(self, name, init_cap): self.trades=[]
        def add_trade(self, t): self.trades.append(t)
        def generate_report(self): print(f"   -> {len(self.trades)} operaciones registradas.")

# =============================================================================
# 3. CONFIGURACIÓN (ECOSYSTEM V5.3)
# =============================================================================

class EcoConfig:
    """Configuración Maestra"""
    INITIAL_CAPITAL = 1000.0
    
    # --- CONTROL DE CAPITAL (SOLUCIÓN A MONTOS IRREALES) ---
    # True = Interés Compuesto | False = Interés Simple (Fijo $1000)
    USE_COMPOUND = True  
    # Si usas compuesto, el lotaje dejará de crecer al llegar a este capital base:
    MAX_CAPITAL_BASE = 2500000.0 
    
    # --- RUTAS DE DATOS (Ajustadas para ejecutarse desde 'tests/') ---
    # La ruta "../" significa "subir un nivel" (salir de tests e ir a la raiz)
    FILE_1D = "../data/historical/AAVEUSDT_1d.csv"
    FILE_4H = "../data/historical/AAVEUSDT_4h.csv"
    FILE_1H = "../data/historical/AAVEUSDT_1h.csv"
    FILE_15M = "../data/historical/AAVEUSDT_15m.csv"
    
    # Parámetros Operativos (Gamma V4.8 Hybrid)
    MAX_RISK_GAMMA = 2
    PCT_CAPITAL_PER_TRADE = 0.15  # 15% por operación
    LEVERAGE = 10                 # 10x Apalancamiento
    
    # Filtros
    G_RSI_PERIOD = 14; G_FILTRO_DIST_FIBO_MAX = 0.008; G_FILTRO_MACD_MIN = 0.0
    G_HEDGE_DIST_FIBO_MIN = 0.012; G_HEDGE_MACD_MAX = -0.01
    
    # SL Dinámico
    G_SL_STRICT = 0.020   # 2.0% para Normales
    G_SL_EXTENDED = 0.020 # 3.0% para Hedges/Shorts
    
    # Salidas Escalonadas
    G_TP_1 = 0.035; G_TP_1_QTY = 0.40     
    G_TP_2 = 0.045; G_TP_2_QTY = 0.30     
    G_BE_ACTIVATION = 0.015; G_BE_PROFIT = 0.005      
    G_TRAILING_DIST = 0.01   

class ShadowConfig:
    """Configuración Shadow V5.0 (Range Eater)"""
    INITIAL_CAPITAL = 1000.0
    BB_PERIOD = 20; BB_STD_DEV = 1.8 
    RSI_MIN_LONG = 35; RSI_MAX_SHORT = 65
    MAX_SLOTS = 5; MIN_SPACING_ATR = 1.0
    USE_MID_BAND_TP = True
    CASHFLOW_TARGET_PCT = 0.80
    SHADOW_TRAILING_PCT = 0.05
    HEDGE_TRIGGER_PNL = -0.020 
    HEDGE_TRAILING_DEV = 0.015
    HEDGE_COOLDOWN_CANDLES = 16
    HEDGE_MIN_PRICE_GAP = 0.010

# =============================================================================
# 4. MOTORES LÓGICOS
# =============================================================================

class EcosystemEngine:
    def __init__(self, df_1h, df_4h, df_1d):
        self.current_capital = EcoConfig.INITIAL_CAPITAL
        self.risk_manager = {'active_trades': []}
        self.reporter = TradingReporter("Ecosystem_Triad_Component", initial_capital=EcoConfig.INITIAL_CAPITAL)
        
        cap_msg = f"Compuesto (Tope ${EcoConfig.MAX_CAPITAL_BASE:,.0f})" if EcoConfig.USE_COMPOUND else "Simple ($1000 Fijo)"
        print(f"   🧠 [Eco Gamma V4.8] Motor Iniciado. Gestión Capital: {cap_msg}")
        
        try:
            self.scanner_1h = StructureScanner(df_1h); self.scanner_1h.precompute()
        except: self.scanner_1h = None 
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
        except: return 999

    def process_candle(self, row_15m, i, full_df_15m):
        ts = row_15m.name
        for trade in list(self.risk_manager['active_trades']):
            self._manage_trade(trade, row_15m)
            if trade['status'] == 'CLOSED': self.risk_manager['active_trades'].remove(trade)
        self._check_gamma(row_15m, ts)

    def _check_gamma(self, row, ts):
        dist_1h = self.get_dist(ts, self.scanner_1h, self.df_1h)
        macd = row['macd_hist']; rsi = row['rsi']
        signal = None; mode = None
        if rsi < 30 and dist_1h < EcoConfig.G_FILTRO_DIST_FIBO_MAX: signal = 'LONG'; mode = 'GAMMA_NORMAL'
        elif rsi > 70 and dist_1h < EcoConfig.G_FILTRO_DIST_FIBO_MAX: signal = 'SHORT'; mode = 'GAMMA_NORMAL'
        elif rsi < 25 and dist_1h > EcoConfig.G_HEDGE_DIST_FIBO_MIN and macd < EcoConfig.G_HEDGE_MACD_MAX: signal = 'SHORT'; mode = 'GAMMA_HEDGE'
        if signal: self._execute_entry(ts, row['close'], signal, mode, 'GAMMA')

    def _execute_entry(self, ts, price, side, mode, strat):
        curr_count = len(self.risk_manager['active_trades'])
        if curr_count >= EcoConfig.MAX_RISK_GAMMA: return
        
        # --- CÁLCULO DE CAPITAL SEGURO (CAP FIXED) ---
        if EcoConfig.USE_COMPOUND:
            # Usa el menor entre (Capital Actual) y (Tope Máximo)
            base_capital = min(self.current_capital, EcoConfig.MAX_CAPITAL_BASE)
        else:
            base_capital = EcoConfig.INITIAL_CAPITAL
            
        margin_usd = base_capital * EcoConfig.PCT_CAPITAL_PER_TRADE
        qty = (margin_usd * EcoConfig.LEVERAGE) / price
        
        trade = {'Trade_ID': f"ECO_{ts.strftime('%d%H%M')}", 'Strategy': strat, 'Mode': mode, 'Side': side,
                 'Entry_Time': ts, 'Entry_Price': price, 'status': 'OPEN', 'Rem_Qty': qty, 'Initial_Qty': qty,
                 'tp1_hit': False, 'tp2_hit': False, 'Max_Adverse_Price': price}
        
        # SL Híbrido (V4.8 Logic)
        sl_pct = EcoConfig.G_SL_EXTENDED if ((mode=='GAMMA_HEDGE') or (side=='SHORT')) else EcoConfig.G_SL_STRICT
        
        if side == 'LONG':
            trade['SL'] = price * (1 - sl_pct)
            trade['TP1_Price'] = price * (1 + EcoConfig.G_TP_1); trade['TP2_Price'] = price * (1 + EcoConfig.G_TP_2)
        else:
            trade['SL'] = price * (1 + sl_pct)
            trade['TP1_Price'] = price * (1 - EcoConfig.G_TP_1); trade['TP2_Price'] = price * (1 - EcoConfig.G_TP_2)
        self.risk_manager['active_trades'].append(trade)

    def _manage_trade(self, trade, row):
        curr = row['close']; ts = row.name
        if trade['Side'] == 'LONG' and curr < trade['Max_Adverse_Price']: trade['Max_Adverse_Price'] = curr
        if trade['Side'] == 'SHORT' and curr > trade['Max_Adverse_Price']: trade['Max_Adverse_Price'] = curr

        if (trade['Side']=='LONG' and curr<=trade['SL']) or (trade['Side']=='SHORT' and curr>=trade['SL']):
            self._close_partial(trade, trade['Rem_Qty'], curr, ts, 'SL_HIT'); return

        if not trade['tp1_hit']:
            if (trade['Side']=='LONG' and curr >= trade['TP1_Price']) or (trade['Side']=='SHORT' and curr <= trade['TP1_Price']):
                qty = min(trade['Initial_Qty'] * EcoConfig.G_TP_1_QTY, trade['Rem_Qty'])
                self._close_partial(trade, qty, curr, ts, 'TP1_HIT'); trade['tp1_hit'] = True
                if trade['Side'] == 'LONG': trade['SL'] = curr * (1 - EcoConfig.G_TRAILING_DIST)
                else: trade['SL'] = curr * (1 + EcoConfig.G_TRAILING_DIST)
                return 

        if not trade['tp2_hit']:
            if (trade['Side']=='LONG' and curr >= trade['TP2_Price']) or (trade['Side']=='SHORT' and curr <= trade['TP2_Price']):
                qty = min(trade['Initial_Qty'] * EcoConfig.G_TP_2_QTY, trade['Rem_Qty'])
                self._close_partial(trade, qty, curr, ts, 'TP2_HIT'); trade['tp2_hit'] = True

        profit_pct = (curr - trade['Entry_Price'])/trade['Entry_Price'] if trade['Side']=='LONG' else (trade['Entry_Price']-curr)/trade['Entry_Price']
        if not trade['tp1_hit'] and profit_pct >= EcoConfig.G_BE_ACTIVATION:
            be_price = trade['Entry_Price'] * (1 + EcoConfig.G_BE_PROFIT) if trade['Side']=='LONG' else trade['Entry_Price'] * (1 - EcoConfig.G_BE_PROFIT)
            if (trade['Side'] == 'LONG' and be_price > trade['SL']) or (trade['Side'] == 'SHORT' and be_price < trade['SL']): trade['SL'] = be_price
        
        if trade['tp1_hit']:
            new_sl = curr * (1 - EcoConfig.G_TRAILING_DIST) if trade['Side']=='LONG' else curr * (1 + EcoConfig.G_TRAILING_DIST)
            if (trade['Side']=='LONG' and new_sl > trade['SL']) or (trade['Side']=='SHORT' and new_sl < trade['SL']): trade['SL'] = new_sl

    def _close_partial(self, trade, qty, price, time, reason):
        if qty <= 0: return
        pnl = (price - trade['Entry_Price']) * qty * (-1 if trade['Side']=='SHORT' else 1)
        self.current_capital += pnl
        if trade['Side']=='LONG': dd = (trade['Max_Adverse_Price']-trade['Entry_Price'])/trade['Entry_Price']
        else: dd = (trade['Entry_Price']-trade['Max_Adverse_Price'])/trade['Entry_Price']
        
        rec = trade.copy(); rec['Exit_Price'] = price; rec['Exit_Time'] = time; rec['Exit_Reason'] = reason
        rec['PnL_Pct'] = (price-trade['Entry_Price'])/trade['Entry_Price'] if trade['Side']=='LONG' else (trade['Entry_Price']-price)/trade['Entry_Price']
        rec['Rem_Qty'] = 0; rec['Closed_Qty'] = qty; rec['Capital_After'] = self.current_capital; rec['Max_DD_During_Trade'] = dd
        self.reporter.add_trade(rec)
        trade['Rem_Qty'] -= qty
        if trade['Rem_Qty'] <= 0.0001: trade['status'] = 'CLOSED'

# --- SHADOW ENGINE V5.0 (Range Eater) ---
class ShadowEngine:
    def __init__(self):
        self.current_capital = ShadowConfig.INITIAL_CAPITAL
        self.positions = {'LONG': [], 'SHORT': []}; self.active_hedges = [] 
        self.reporter = TradingReporter("Shadow_Triad_Component", initial_capital=ShadowConfig.INITIAL_CAPITAL)
        print(f"   🛡️ [Shadow V5.0] Motor Activo (Swing Enhanced).")

    def process_candle(self, row):
        price = row['close']; atr = row['atr']; rsi = row['rsi']
        for hedge in self.active_hedges[:]:
            self._manage_hedge(hedge, row)
            if hedge['status'] == 'CLOSED': self.active_hedges.remove(hedge)
        for side in ['LONG', 'SHORT']:
            for pos in self.positions[side][:]:
                self._manage_main_pos(pos, row)
                if pos['qty_total'] <= 0.0001: self.positions[side].remove(pos)
        upper = row['bb_upper']; lower = row['bb_lower']
        if row['high'] >= upper and rsi > ShadowConfig.RSI_MAX_SHORT and self._can_open('SHORT', price, atr):
            size_usd = self.current_capital / ShadowConfig.MAX_SLOTS; qty = size_usd / price
            self._open_pos('SHORT', price, qty, row, size_usd)
        if row['low'] <= lower and rsi < ShadowConfig.RSI_MIN_LONG and self._can_open('LONG', price, atr):
            size_usd = self.current_capital / ShadowConfig.MAX_SLOTS; qty = size_usd / price
            self._open_pos('LONG', price, qty, row, size_usd)

    def _manage_main_pos(self, pos, row):
        curr = row['close']; entry = pos['entry_price']
        pnl_pct = (curr - entry)/entry if pos['side']=='LONG' else (entry - curr)/entry
        if pnl_pct > pos['max_pnl']: pos['max_pnl'] = pnl_pct
        has_hedge = any(h['parent_id'] == pos['id'] for h in self.active_hedges)
        if pnl_pct < ShadowConfig.HEDGE_TRIGGER_PNL and not has_hedge:
            if self._is_hedge_allowed(pos, curr, row.name): self._activate_hedge(pos, curr, row.name)
        bb_mid = row['bb_mid']
        if not pos.get('tp1_hit', False):
            if (pos['side']=='LONG' and row['high'] >= bb_mid) or (pos['side']=='SHORT' and row['low'] <= bb_mid):
                qty = min(pos['initial_qty'] * 0.50, pos['qty_total'])
                self._close_main_partial(pos, qty, bb_mid, row.name, 'TP1_MID_BAND'); pos['tp1_hit'] = True; return
        bb_width = row['bb_width'] * row['bb_mid']
        target = entry + (bb_width * ShadowConfig.CASHFLOW_TARGET_PCT) if pos['side']=='LONG' else entry - (bb_width * ShadowConfig.CASHFLOW_TARGET_PCT)
        if (pos['side']=='LONG' and row['high']>=target) or (pos['side']=='SHORT' and row['low']<=target):
            self._close_main_partial(pos, pos['qty_total'], target, row.name, 'TARGET_HIT'); return
        if pos['max_pnl'] > 0.01: 
            trigger = pos['max_pnl'] - ShadowConfig.SHADOW_TRAILING_PCT
            if pnl_pct < trigger and pnl_pct > 0: self._close_main_partial(pos, pos['qty_total'], curr, row.name, 'TRAILING_STOP')

    def _is_hedge_allowed(self, pos, curr_price, curr_time):
        last_time = pos.get('last_hedge_exit_time')
        if last_time and (curr_time - last_time).total_seconds() / 900 < ShadowConfig.HEDGE_COOLDOWN_CANDLES: return False
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
        pnl_usd = (price - hedge['entry_price']) * hedge['qty'] * (-1 if hedge['side']=='SHORT' else 1)
        self.current_capital += pnl_usd
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
               'qty_total': qty, 'initial_qty': qty, 'max_pnl': 0.0, 'invested_usd': invested_usd, 
               'last_hedge_exit_time': None, 'last_hedge_entry_price': None, 'tp1_hit': False}
        self.positions[side].append(pos)

    def _close_main_partial(self, pos, qty, price, time, reason):
        for hedge in self.active_hedges:
            if hedge['parent_id'] == pos['id']: self._close_hedge(hedge, price, time)
        pnl_usd = (price - pos['entry_price']) * qty * (-1 if pos['side']=='SHORT' else 1)
        self.current_capital += pnl_usd
        trade = {'Trade_ID': pos['id'], 'Strategy': 'SHADOW_V5', 'Side': pos['side'], 'Entry_Time': pos['entry_time'], 'Exit_Time': time,
                 'PnL_Pct': (price - pos['entry_price'])/pos['entry_price'] if pos['side']=='LONG' else (pos['entry_price']-price)/pos['entry_price'],
                 'Rem_Qty': 0, 'Closed_Qty': qty, 'Capital_After': self.current_capital, 'Exit_Reason': reason}
        self.reporter.add_trade(trade); pos['qty_total'] -= qty

class TriadOrchestrator:
    def __init__(self):
        print("\n🎹 INICIANDO SIMULACIÓN TRÍADA V5.3 (PATH DEBUG & CAP FIX)...")
        self.load_and_prepare_data()
        self.eco_engine = EcosystemEngine(self.df_1h, self.df_4h, self.df_1d)
        self.shadow_engine = ShadowEngine()

    def load_and_prepare_data(self):
        print("⏳ Cargando y Sincronizando Datos...")
        def load(f):
            # --- CORRECCIÓN DE RUTAS ABSOLUTAS ---
            base_path = os.path.dirname(os.path.abspath(__file__))
            p = os.path.normpath(os.path.join(base_path, f))
            
            print(f"   🔎 Buscando archivo: {p}") # DEBUG PRINT
            
            if not os.path.exists(p):
                print(f"   ❌ NO ENCONTRADO. Usando Fallback Data Dummy (Seed 42).")
                # Data Dummy Determinista
                dates = pd.date_range(end=datetime.now(), periods=2000, freq='15min')
                close = [100.0]
                for _ in range(len(dates)-1): close.append(close[-1] * (1 + np.random.uniform(-0.01, 0.01)))
                df = pd.DataFrame({'timestamp': dates, 'open': close, 'high': [c*1.005 for c in close], 
                                   'low': [c*0.995 for c in close], 'close': close, 'volume': 1000})
                df.set_index('timestamp', inplace=True)
                return df
            
            df = pd.read_csv(p)
            df.columns = [c.lower().strip() for c in df.columns]
            if 'timestamp' in df.columns: df['timestamp'] = pd.to_datetime(df['timestamp']); df.set_index('timestamp', inplace=True)
            return df.dropna()

        self.df_15m = load(EcoConfig.FILE_15M); self.df_1h = load(EcoConfig.FILE_1H)
        self.df_4h = load(EcoConfig.FILE_4H); self.df_1d = load(EcoConfig.FILE_1D)

        df = self.df_15m.copy()
        delta = df['close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 0.0001))))
        k = df['close'].ewm(span=12).mean(); d = df['close'].ewm(span=26).mean()
        df['macd_hist'] = (k-d) - (k-d).ewm(span=9).mean()
        sma = df['close'].rolling(20).mean(); std = df['close'].rolling(20).std()
        df['bb_upper'] = sma + (std*2); df['bb_lower'] = sma - (std*2); df['bb_mid'] = sma; df['bb_width'] = df['bb_upper'] - df['bb_lower']
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
        print("\n" + "="*50); print("🏁 SIMULACIÓN FINALIZADA - RESULTADOS"); print("="*50)
        print(f"\n📘 REPORTE GAMMA (Capital Final: ${self.eco_engine.current_capital:,.2f}):")
        self.eco_engine.reporter.generate_report()
        print(f"\n🛡️ REPORTE SHADOW V5.0 (Capital Final: ${self.shadow_engine.current_capital:,.2f}):")
        self.shadow_engine.reporter.generate_report()

if __name__ == "__main__":
    triad = TriadOrchestrator()
    triad.run_simulation()