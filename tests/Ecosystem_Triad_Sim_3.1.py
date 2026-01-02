# =============================================================================
# NOMBRE: Ecosystem_Triad_Sim_3.py
# VERSIÓN: 3.0 (Compound Interest + No Swing)
# DESCRIPCIÓN: 
#   - Gamma V7: Activo con Interés Compuesto (Sizing Dinámico).
#   - Swing V3: DESACTIVADO (Para prueba de eficiencia).
#   - Shadow V2: Activo con Interés Compuesto (Grid Dinámico).
#
# CAPITAL INICIAL: $1,000 por Motor (Se reinvierten ganancias).
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
    print("✅ Tríada Simulator V3 (Compound Mode): Librerías cargadas.")
except ImportError as e:
    print(f"❌ Error Crítico: {e}")
    sys.exit(1)

# =============================================================================
# 2. CONFIGURACIONES
# =============================================================================

class EcoConfig:
    """Configuración para Gamma (Swing Desactivado)"""
    INITIAL_CAPITAL = 1000.0
    
    # Rutas (Idénticas al original)
    FILE_1D = "../data/historical/AAVEUSDT_1d.csv"
    FILE_4H = "../data/historical/AAVEUSDT_4h.csv"
    FILE_1H = "../data/historical/AAVEUSDT_1h.csv"
    FILE_15M = "../data/historical/AAVEUSDT_15m.csv"
    
    # Gestión de Riesgo (COMPOUND)
    MAX_RISK_GAMMA = 2  # Max operaciones simultáneas
    # Porcentaje del capital TOTAL asignado a cada operación de Gamma
    # Si hay 2 cupos, usamos el 45% por operación para dejar un margen de error.
    PCT_CAPITAL_PER_TRADE = 0.45 
    
    # Parámetros Gamma V7
    G_RSI_PERIOD = 14
    G_FILTRO_DIST_FIBO_MAX = 0.008
    G_FILTRO_MACD_MIN = 0.0
    G_HEDGE_DIST_FIBO_MIN = 0.012
    G_HEDGE_MACD_MAX = -0.01
    G_TP_NORMAL = 0.035; G_SL_NORMAL = 0.020; G_TRAIL_NORM = 0.50
    G_TP_HEDGE = 0.045;  G_SL_HEDGE = 0.015;  G_TRAIL_HEDGE = 0.30

class ShadowConfig:
    """Configuración para ShadowHunter V2 (Compound)"""
    INITIAL_CAPITAL = 1000.0
    # Parámetros
    BB_PERIOD = 20
    BB_STD_DEV = 2.0
    
    MAX_SLOTS = 5
    # COMPOUND: En lugar de $100 fijos, usamos (Capital / MAX_SLOTS)
    # Esto asegura que si el capital crece, el tamaño del Grid crece.
    
    MIN_SPACING_ATR = 1.0
    CASHFLOW_TARGET_PCT = 0.80
    SHADOW_TRAILING_PCT = 0.05

# =============================================================================
# 3. MOTORES LÓGICOS (BRAINS)
# =============================================================================

# --- MOTOR 1: ECOSISTEMA (Gamma Only - Swing Disabled) ---
class EcosystemEngine:
    def __init__(self, df_1h, df_4h, df_1d):
        self.current_capital = EcoConfig.INITIAL_CAPITAL  # Capital Dinámico
        self.risk_manager = {'active_trades': []}
        # Nota: El reporter recibirá el capital inicial, pero nosotros gestionamos el crecimiento internamente
        self.reporter = TradingReporter("Ecosystem_Triad_Component", initial_capital=EcoConfig.INITIAL_CAPITAL)
        
        print(f"   🧠 [Eco] Motor Iniciado. Capital: ${self.current_capital:.2f} (Swing OFF)")
        self.scanner_1h = StructureScanner(df_1h); self.scanner_1h.precompute()
        # self.scanner_4h = StructureScanner(df_4h) # No necesario sin Swing
        
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
        
        # 1. Gestión de Trades
        for trade in list(self.risk_manager['active_trades']):
            self._manage_trade(trade, row_15m)
            if trade['status'] == 'CLOSED':
                # Al cerrar, actualizamos el Capital Real con el PnL en USD
                pnl_usd = (trade['Exit_Price'] - trade['Entry_Price']) * trade['Rem_Qty']
                if trade['Side'] == 'SHORT': pnl_usd *= -1
                
                self.current_capital += pnl_usd # Interés Compuesto
                
                # Actualizar trade con datos finales para el reporte
                trade['Capital_After'] = self.current_capital
                self.reporter.add_trade(trade)
                self.risk_manager['active_trades'].remove(trade)

        # 2. Señal Swing (DESACTIVADA POR SOLICITUD)
        # if ts.minute == 0:
        #     self._check_swing(ts)

        # 3. Señal Gamma (Solo Scalping)
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

        # --- LÓGICA DE INTERÉS COMPUESTO ---
        # Calculamos el tamaño de la posición basándonos en el capital ACTUAL
        allocated_usd = self.current_capital * EcoConfig.PCT_CAPITAL_PER_TRADE
        qty = allocated_usd / price  # Cantidad de tokens a comprar/vender
        
        trade = {
            'Trade_ID': f"ECO_{ts.strftime('%d%H%M')}",
            'Strategy': strat, 'Mode': mode, 'Side': side,
            'Entry_Time': ts, 'Entry_Price': price,
            'status': 'OPEN', 'Peak_Price': price, 
            'Rem_Qty': qty, # Cantidad real dinámica
            'Invested_USD': allocated_usd
        }
        
        sl_pct = EcoConfig.G_SL_NORMAL if 'NORMAL' in mode else EcoConfig.G_SL_HEDGE
        tp_pct = EcoConfig.G_TP_NORMAL

        trade['SL'] = price * (1 - sl_pct) if side == 'LONG' else price * (1 + sl_pct)
        trade['TP_Target'] = price * (1 + tp_pct) if side == 'LONG' else price * (1 - tp_pct)
        
        self.risk_manager['active_trades'].append(trade)

    def _manage_trade(self, trade, row):
        curr = row['close']
        # SL Check
        if (trade['Side']=='LONG' and curr<=trade['SL']) or (trade['Side']=='SHORT' and curr>=trade['SL']):
            self._close(trade, curr, row.name, 'SL_HIT')
            return
        
        # Trailing
        dist = abs(trade['Entry_Price'] - curr) / trade['Entry_Price']
        if dist > 0.015: 
            new_sl = curr * 0.995 if trade['Side']=='LONG' else curr * 1.005
            if trade['Side']=='LONG' and new_sl > trade['SL']: trade['SL'] = new_sl
            if trade['Side']=='SHORT' and new_sl < trade['SL']: trade['SL'] = new_sl

    def _close(self, trade, price, time, reason):
        trade['Exit_Price'] = price; trade['Exit_Time'] = time; trade['Exit_Reason'] = reason
        trade['status'] = 'CLOSED'
        # PnL %
        trade['PnL_Pct'] = (price - trade['Entry_Price'])/trade['Entry_Price'] if trade['Side']=='LONG' else (trade['Entry_Price']-price)/trade['Entry_Price']


# --- MOTOR 2: SHADOW HUNTER (Compound Grid) ---
class ShadowEngine:
    def __init__(self):
        self.current_capital = ShadowConfig.INITIAL_CAPITAL
        self.positions = {'LONG': [], 'SHORT': []}
        self.reporter = TradingReporter("Shadow_Triad_Component", initial_capital=ShadowConfig.INITIAL_CAPITAL)
        print(f"   👻 [Shadow] Motor Iniciado. Capital: ${self.current_capital:.2f} (Compound ON)")

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
        
        if row['high'] >= upper and self._can_open('SHORT', price, atr):
            # COMPOUND SIZING: Dividimos el capital actual entre los slots máximos
            size_usd = self.current_capital / ShadowConfig.MAX_SLOTS
            qty = size_usd / price
            self._open_pos('SHORT', price, qty, row, size_usd)
            
        if row['low'] <= lower and self._can_open('LONG', price, atr):
            size_usd = self.current_capital / ShadowConfig.MAX_SLOTS
            qty = size_usd / price
            self._open_pos('LONG', price, qty, row, size_usd)

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
            'invested_usd': invested_usd
        }
        self.positions[side].append(pos)

    def _manage_pos(self, pos, row):
        curr = row['close']
        entry = pos['entry_price']
        bb_width = row['bb_width'] * row['bb_mid']
        
        pnl_pct = (curr - entry)/entry if pos['side']=='LONG' else (entry - curr)/entry
        if pnl_pct > pos['max_pnl']: pos['max_pnl'] = pnl_pct
        
        target = entry + (bb_width * ShadowConfig.CASHFLOW_TARGET_PCT) if pos['side']=='LONG' else entry - (bb_width * ShadowConfig.CASHFLOW_TARGET_PCT)
        
        hit_tp = (pos['side']=='LONG' and row['high']>=target) or (pos['side']=='SHORT' and row['low']<=target)
        if hit_tp:
            self._close(pos, target, row.name, 'TARGET_HIT')
            return

        if pos['max_pnl'] > 0.01: 
            trigger = pos['max_pnl'] - ShadowConfig.SHADOW_TRAILING_PCT
            if pnl_pct < trigger and pnl_pct > 0:
                self._close(pos, curr, row.name, 'TRAILING_STOP')

    def _close(self, pos, price, time, reason):
        # Calcular Ganancia en USD
        pnl_usd = (price - pos['entry_price']) * pos['qty_total']
        if pos['side'] == 'SHORT': pnl_usd *= -1
        
        # ACTUALIZAR CAPITAL (Interés Compuesto)
        self.current_capital += pnl_usd
        
        trade = {
            'Trade_ID': pos['id'], 'Strategy': 'SHADOW_V2', 'Side': pos['side'],
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
        print("\n🎹 INICIANDO SIMULACIÓN TRÍADA V3 (COMPOUND + NO SWING)...")
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
        print("🚀 Ejecutando Loop Sincronizado (Compound Mode)...")
        for i in range(len(self.df_15m)):
            row = self.df_15m.iloc[i]
            self.shadow_engine.process_candle(row)
            self.eco_engine.process_candle(row, i, self.df_15m)

        print("\n" + "="*50)
        print("🏁 SIMULACIÓN V3 FINALIZADA - RESULTADOS (REAL COMPOUND)")
        print("="*50)
        
        print(f"\n📘 REPORTE GAMMA (Capital Final: ${self.eco_engine.current_capital:,.2f}):")
        self.eco_engine.reporter.generate_report()
        
        print(f"\n📙 REPORTE SHADOW (Capital Final: ${self.shadow_engine.current_capital:,.2f}):")
        self.shadow_engine.reporter.generate_report()

if __name__ == "__main__":
    triad = TriadOrchestrator()
    triad.run_simulation()