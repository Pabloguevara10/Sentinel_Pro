# =============================================================================
# NOMBRE: Ecosystem_Triad_Sim.py
# TIPO: Simulador Integral (La Tríada)
# DESCRIPCIÓN: Ejecuta simultáneamente 3 lógicas de trading:
#   1. TrendHunter Gamma V7 (Scalping Estructural)
#   2. SwingHunter Alpha V3 (Swing Estructural)
#   3. ShadowHunter V2 (Mean Reversion en Cascada)
#
# CAPITAL: $1,000 para Ecosistema (1 & 2) | $1,000 para ShadowHunter (3)
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
    # Usamos la versión _2 como solicitaste para el Ecosistema
    from StructureScanner_2 import StructureScanner
    from Reporter import TradingReporter
    print("✅ Tríada Simulator: Librerías cargadas correctamente.")
except ImportError as e:
    print(f"❌ Error Crítico: {e}")
    sys.exit(1)

# =============================================================================
# 2. CONFIGURACIONES (SEPARADAS PARA EVITAR CONFLICTOS)
# =============================================================================

class EcoConfig:
    """Configuración para Gamma y Swing"""
    INITIAL_CAPITAL = 1000
    # Rutas
    FILE_1D = "../data/historical/AAVEUSDT_1d.csv"
    FILE_4H = "../data/historical/AAVEUSDT_4h.csv"
    FILE_1H = "../data/historical/AAVEUSDT_1h.csv"
    FILE_15M = "../data/historical/AAVEUSDT_15m.csv"
    
    # Límites
    MAX_RISK_GAMMA = 2; MAX_RISK_SWING = 2; MAX_RISK_TOTAL = 3
    
    # Gamma V7
    G_RSI_PERIOD = 14
    G_FILTRO_DIST_FIBO_MAX = 0.008
    G_FILTRO_MACD_MIN = 0.0
    G_HEDGE_DIST_FIBO_MIN = 0.012
    G_HEDGE_MACD_MAX = -0.01
    G_TP_NORMAL = 0.035; G_SL_NORMAL = 0.020; G_TRAIL_NORM = 0.50
    G_TP_HEDGE = 0.045;  G_SL_HEDGE = 0.015;  G_TRAIL_HEDGE = 0.30

    # Swing V3
    S_FILTRO_DIST_FIBO_MACRO = 0.025
    S_FILTRO_MACD_MIN = 0.0
    S_HEDGE_DIST_FIBO_MIN = 0.050
    S_HEDGE_MACD_MAX = -0.05
    S_SL_INIT_NORM = 0.06; S_TP1_DIST = 0.06; S_TP2_DIST = 0.12

class ShadowConfig:
    """Configuración para ShadowHunter V2"""
    INITIAL_CAPITAL = 1000
    # Parámetros
    BB_PERIOD = 20
    BB_STD_DEV = 2.0
    BASE_UNIT_USD = 100.0
    MAX_SLOTS = 5
    MIN_SPACING_ATR = 1.0
    CASHFLOW_TARGET_PCT = 0.80
    SHADOW_TRAILING_PCT = 0.05
    MAX_ADD_ONS = 1

# =============================================================================
# 3. MOTORES LÓGICOS (BRAINS)
# =============================================================================

# --- MOTOR 1: ECOSISTEMA (Gamma + Swing) ---
class EcosystemEngine:
    def __init__(self, df_1h, df_4h, df_1d):
        self.risk_manager = {'active_trades': []} # Simplificado
        self.reporter = TradingReporter("Ecosystem_Triad_Component", initial_capital=EcoConfig.INITIAL_CAPITAL)
        
        # Scanners Contextuales
        print("   🧠 [Eco] Inicializando Scanners Fibo...")
        self.scanner_1h = StructureScanner(df_1h); self.scanner_1h.precompute()
        self.scanner_4h = StructureScanner(df_4h); self.scanner_4h.precompute()
        self.scanner_1d = StructureScanner(df_1d); self.scanner_1d.precompute()
        
        self.df_1h = df_1h
        self.df_4h = df_4h
        self.df_1d = df_1d

    def get_dist(self, ts, scanner, df):
        idx = df.index.get_indexer([ts], method='pad')[0]
        if idx == -1: return 999
        ctx = scanner.get_fibonacci_context(idx)
        if not ctx: return 999
        price = df.iloc[idx]['close']
        return min([abs(price-l)/price for l in ctx['fibs'].values()])

    def process_candle(self, row_15m, i, full_df_15m):
        ts = row_15m.name
        
        # 1. Gestión de Trades Activos (Trailing/TP/SL)
        for trade in list(self.risk_manager['active_trades']):
            self._manage_trade(trade, row_15m)
            if trade['status'] == 'CLOSED':
                self.reporter.add_trade(trade)
                self.risk_manager['active_trades'].remove(trade)

        # 2. Señal Swing (Inicio de hora)
        if ts.minute == 0:
            self._check_swing(ts)

        # 3. Señal Gamma (Cada 15m)
        self._check_gamma(row_15m, ts)

    def _check_gamma(self, row, ts):
        # Lógica Gamma V7 (Resumida)
        dist_1h = self.get_dist(ts, self.scanner_1h, self.df_1h)
        macd = row['macd_hist']; rsi = row['rsi']
        
        # Simplificación de señal para integración
        signal = None; mode = None
        
        if rsi < 30 and dist_1h < EcoConfig.G_FILTRO_DIST_FIBO_MAX:
            signal = 'LONG'; mode = 'GAMMA_NORMAL'
        elif rsi > 70 and dist_1h < EcoConfig.G_FILTRO_DIST_FIBO_MAX:
            signal = 'SHORT'; mode = 'GAMMA_NORMAL'
        # Hedge Logic
        elif rsi < 25 and dist_1h > EcoConfig.G_HEDGE_DIST_FIBO_MIN and macd < EcoConfig.G_HEDGE_MACD_MAX:
            signal = 'SHORT'; mode = 'GAMMA_HEDGE' # Reversal Counter-Trend (Judo)
        
        if signal: self._execute_entry(ts, row['close'], signal, mode, 'GAMMA')

    def _check_swing(self, ts):
        # Lógica Swing V3 (Resumida)
        idx = self.df_1h.index.get_indexer([ts], method='pad')[0]
        if idx == -1: return
        row_1h = self.df_1h.iloc[idx]
        
        d4 = self.get_dist(ts, self.scanner_4h, self.df_4h)
        if row_1h['rsi'] < 35 and d4 < EcoConfig.S_FILTRO_DIST_FIBO_MACRO:
             self._execute_entry(ts, row_1h['close'], 'LONG', 'SWING_NORMAL', 'SWING')

    def _execute_entry(self, ts, price, side, mode, strat):
        # Filtro de Cupos básico
        curr_count = len([t for t in self.risk_manager['active_trades'] if t['Strategy']==strat])
        limit = EcoConfig.MAX_RISK_GAMMA if strat == 'GAMMA' else EcoConfig.MAX_RISK_SWING
        if curr_count >= limit: return

        trade = {
            'Trade_ID': f"ECO_{ts.strftime('%d%H%M')}",
            'Strategy': strat, 'Mode': mode, 'Side': side,
            'Entry_Time': ts, 'Entry_Price': price,
            'status': 'OPEN', 'Peak_Price': price, 'Rem_Qty': 1.0
        }
        
        # SL/TP Setup
        if strat == 'GAMMA':
            sl_pct = EcoConfig.G_SL_NORMAL if 'NORMAL' in mode else EcoConfig.G_SL_HEDGE
            tp_pct = EcoConfig.G_TP_NORMAL
        else:
            sl_pct = EcoConfig.S_SL_INIT_NORM
            tp_pct = EcoConfig.S_TP2_DIST

        trade['SL'] = price * (1 - sl_pct) if side == 'LONG' else price * (1 + sl_pct)
        trade['TP_Target'] = price * (1 + tp_pct) if side == 'LONG' else price * (1 - tp_pct)
        
        self.risk_manager['active_trades'].append(trade)

    def _manage_trade(self, trade, row):
        curr = row['close']
        # SL Check
        if (trade['Side']=='LONG' and curr<=trade['SL']) or (trade['Side']=='SHORT' and curr>=trade['SL']):
            self._close(trade, curr, row.name, 'SL_HIT')
            return
        
        # Trailing Simple
        if trade['Strategy'] == 'GAMMA':
            dist = abs(trade['Entry_Price'] - curr) / trade['Entry_Price']
            if dist > 0.015: # Activar trailing al 1.5%
                new_sl = curr * 0.995 if trade['Side']=='LONG' else curr * 1.005
                if trade['Side']=='LONG' and new_sl > trade['SL']: trade['SL'] = new_sl
                if trade['Side']=='SHORT' and new_sl < trade['SL']: trade['SL'] = new_sl

    def _close(self, trade, price, time, reason):
        trade['Exit_Price'] = price; trade['Exit_Time'] = time; trade['Exit_Reason'] = reason
        trade['status'] = 'CLOSED'
        trade['PnL_Pct'] = (price - trade['Entry_Price'])/trade['Entry_Price'] if trade['Side']=='LONG' else (trade['Entry_Price']-price)/trade['Entry_Price']


# --- MOTOR 2: SHADOW HUNTER (Cascada) ---
class ShadowEngine:
    def __init__(self):
        self.positions = {'LONG': [], 'SHORT': []}
        self.reporter = TradingReporter("Shadow_Triad_Component", initial_capital=ShadowConfig.INITIAL_CAPITAL)
        print("   👻 [Shadow] Inicializando Motor Cascada...")

    def process_candle(self, row):
        price = row['close']
        atr = row['atr']
        
        # 1. Gestionar Posiciones
        for side in ['LONG', 'SHORT']:
            for pos in self.positions[side][:]:
                self._manage_pos(pos, row)
                if pos['qty_total'] <= 0.0001:
                    self.positions[side].remove(pos)
        
        # 2. Buscar Entradas
        upper = row['bb_upper']; lower = row['bb_lower']
        
        # Short Entry (Touch Upper Band)
        if row['high'] >= upper and self._can_open('SHORT', price, atr):
            qty = ShadowConfig.BASE_UNIT_USD / price
            self._open_pos('SHORT', price, qty, row)
            
        # Long Entry (Touch Lower Band)
        if row['low'] <= lower and self._can_open('LONG', price, atr):
            qty = ShadowConfig.BASE_UNIT_USD / price
            self._open_pos('LONG', price, qty, row)

    def _can_open(self, side, price, atr):
        actives = self.positions[side]
        if len(actives) >= ShadowConfig.MAX_SLOTS: return False
        if actives:
            last = actives[-1]['entry_price']
            if abs(price - last) < (atr * ShadowConfig.MIN_SPACING_ATR): return False
        return True

    def _open_pos(self, side, price, qty, row):
        pos = {
            'id': f"SHADOW_{side[0]}_{row.name.strftime('%d%H%M')}",
            'side': side, 'entry_price': price, 'entry_time': row.name,
            'qty_total': qty, 'max_pnl': 0.0
        }
        self.positions[side].append(pos)

    def _manage_pos(self, pos, row):
        curr = row['close']
        entry = pos['entry_price']
        bb_width = row['bb_width'] * row['bb_mid']
        
        # PnL Calc
        pnl_pct = (curr - entry)/entry if pos['side']=='LONG' else (entry - curr)/entry
        if pnl_pct > pos['max_pnl']: pos['max_pnl'] = pnl_pct
        
        # Target Cashflow (Band Width based)
        target = entry + (bb_width * ShadowConfig.CASHFLOW_TARGET_PCT) if pos['side']=='LONG' else entry - (bb_width * ShadowConfig.CASHFLOW_TARGET_PCT)
        
        # Salida por Target
        hit_tp = (pos['side']=='LONG' and row['high']>=target) or (pos['side']=='SHORT' and row['low']<=target)
        if hit_tp:
            self._close(pos, target, row.name, 'TARGET_HIT')
            return

        # Salida por Trailing (Shadow)
        if pos['max_pnl'] > 0.01: # 1% Min gain
            trigger = pos['max_pnl'] - ShadowConfig.SHADOW_TRAILING_PCT
            if pnl_pct < trigger and pnl_pct > 0:
                self._close(pos, curr, row.name, 'TRAILING_STOP')

    def _close(self, pos, price, time, reason):
        trade = {
            'Trade_ID': pos['id'], 'Strategy': 'SHADOW_V2', 'Side': pos['side'],
            'Entry_Time': pos['entry_time'], 'Entry_Price': pos['entry_price'],
            'Exit_Time': time, 'Exit_Price': price, 'Exit_Reason': reason,
            'PnL_Pct': (price - pos['entry_price'])/pos['entry_price'] if pos['side']=='LONG' else (pos['entry_price']-price)/pos['entry_price']
        }
        self.reporter.add_trade(trade)
        pos['qty_total'] = 0

# =============================================================================
# 4. ORQUESTADOR PRINCIPAL (THE CONDUCTOR)
# =============================================================================
class TriadOrchestrator:
    def __init__(self):
        print("\n🎹 INICIANDO SIMULACIÓN TRÍADA (ECOSISTEMA + SHADOW)...")
        self.load_and_prepare_data()
        
        # Inicializar Motores
        self.eco_engine = EcosystemEngine(self.df_1h, self.df_4h, self.df_1d)
        self.shadow_engine = ShadowEngine()

    def load_and_prepare_data(self):
        print("⏳ Cargando y Sincronizando Datos...")
        # Helper de carga
        def load(f):
            p = os.path.join(os.path.dirname(__file__), f)
            df = pd.read_csv(p)
            df.columns = [c.lower().strip() for c in df.columns]
            # Fix timestamps
            if 'timestamp' in df.columns:
                 # Detector simple de ms vs sec
                if df['timestamp'].iloc[0] > 10000000000:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            return df.dropna()

        # Cargar Dataframes
        self.df_15m = load(EcoConfig.FILE_15M)
        self.df_1h = load(EcoConfig.FILE_1H)
        self.df_4h = load(EcoConfig.FILE_4H)
        self.df_1d = load(EcoConfig.FILE_1D) # Para Swing Macro

        # --- PREPARACIÓN DE INDICADORES UNIFICADA ---
        # 1. Indicadores Eco (RSI, MACD)
        df = self.df_15m.copy()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        k = df['close'].ewm(span=12).mean(); d = df['close'].ewm(span=26).mean()
        df['macd_hist'] = (k-d) - (k-d).ewm(span=9).mean()

        # 2. Indicadores Shadow (Bollinger, ATR)
        sma = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std()
        df['bb_upper'] = sma + (std * 2)
        df['bb_lower'] = sma - (std * 2)
        df['bb_mid'] = sma
        df['bb_width'] = df['bb_upper'] - df['bb_lower']
        
        # ATR Manual
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - df['close'].shift(1)).abs()
        tr3 = (df['low'] - df['close'].shift(1)).abs()
        df['atr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()
        
        self.df_15m = df.dropna()
        print(f"✅ Data Lista: {len(self.df_15m)} velas 15m sincronizadas.")

    def run_simulation(self):
        print("🚀 Ejecutando Loop Sincronizado...")
        
        # Loop Principal (Vela a Vela)
        for i in range(len(self.df_15m)):
            row = self.df_15m.iloc[i]
            
            # 1. Turno ShadowHunter
            self.shadow_engine.process_candle(row)
            
            # 2. Turno Ecosistema
            self.eco_engine.process_candle(row, i, self.df_15m)

        # Generar Reportes Finales
        print("\n" + "="*50)
        print("🏁 SIMULACIÓN FINALIZADA - RESULTADOS")
        print("="*50)
        
        print("\n📘 REPORTE ECOSISTEMA (Gamma + Swing):")
        self.eco_engine.reporter.generate_report()
        
        print("\n📙 REPORTE SHADOW HUNTER (Cascada):")
        self.shadow_engine.reporter.generate_report()

if __name__ == "__main__":
    triad = TriadOrchestrator()
    triad.run_simulation()