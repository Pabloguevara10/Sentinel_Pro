# =============================================================================
# NOMBRE: Forensic_Sentinel_Final.py
# VERSIÓN: 3.2 (Calibración Final S/L 2.5%)
# DESCRIPCIÓN: Simulador con Protocolo de Acecho (Stalker), Trailing Perezoso
# y Stop Loss ajustado al 2.5% para cubrir el drawdown natural de AAVE.
# =============================================================================

import pandas as pd
import numpy as np
import os
import sys
from collections import deque
from datetime import datetime, timedelta
from scipy.stats import linregress

# =============================================================================
# 1. CONFIGURACIÓN
# =============================================================================
class Config:
    DATA_DIR = "data/historical"
    FILES = {
        '1h': "AAVEUSDT_1h.csv",
        '15m': "AAVEUSDT_15m.csv",
        '5m': "AAVEUSDT_5m.csv",
        '1m': "AAVEUSDT_1m.csv"
    }
    
    # --- GESTIÓN DE RIESGO (CALIBRADO) ---
    SL_PCT = 0.025            # Stop Loss: 2.5% (Ajuste Solicitado)
    TP_ACTIVATION = 0.015     # Activar Trailing tras +1.5%
    TRAILING_GAP = 0.010      # Distancia Trailing 1%
    
    # --- PROTOCOLO DE ACECHO (STALKING) ---
    RSI_SHAKEOUT_SLOPE = 2.0  # Pendiente mínima para considerar "Latigazo"
    STALK_TIMEOUT_MIN = 60    # Tiempo máximo de espera
    TRIGGER_TIMEOUT_MIN = 15  # Tiempo para romper el trigger una vez armado
    
    # --- INDICADORES ---
    BB_DEV = 2.0

# =============================================================================
# 2. MOTOR DE DATOS E INDICADORES
# =============================================================================
class DataLoader:
    def __init__(self):
        self.dfs = {}
    
    def load_all(self):
        print("📂 Cargando Datos (Configuración Final 2.5%)...")
        for tf, fname in Config.FILES.items():
            path = os.path.join(Config.DATA_DIR, fname)
            if not os.path.exists(path): path = fname
            
            if os.path.exists(path):
                df = pd.read_csv(path)
                if 'timestamp' in df.columns:
                    if df['timestamp'].iloc[0] > 10000000000:
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    else:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                else:
                    df.index = pd.to_datetime(df.index)
                
                self.dfs[tf] = self._calc_indicators(df, tf)
                print(f"   ✅ {tf}: {len(df)} velas.")
            else:
                print(f"   ❌ Error: Falta {fname}")
                sys.exit(1)

    def _calc_indicators(self, df, tf_name):
        cols = ['open', 'high', 'low', 'close', 'volume']
        for c in cols: 
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce')
        
        # Bollinger
        df['bb_mid'] = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std()
        df['bb_up'] = df['bb_mid'] + (Config.BB_DEV * std)
        df['bb_low'] = df['bb_mid'] - (Config.BB_DEV * std)
        
        denom = df['bb_up'] - df['bb_low']
        # Safe division
        df['bb_pos'] = np.where(denom == 0, 0.5, (df['close'] - df['bb_low']) / denom)

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # RSI Slope
        df['rsi_slope'] = df['rsi'].diff(3)
        
        # Fix FutureWarning
        return df.bfill()

    def get_context(self, ts):
        ctx = {}
        for tf, df in self.dfs.items():
            idx = df.index.asof(ts)
            if pd.isna(idx): return None
            ctx[tf] = df.loc[idx]
        return ctx

# =============================================================================
# 3. GESTIÓN DE ORDENES (Exchange Virtual)
# =============================================================================
class VirtualExchange:
    def __init__(self):
        self.positions = {} 
        self.closed_trades = []

    def abrir(self, strategy_id, entry_price, side, time_idx, metadata=None):
        if strategy_id not in self.positions:
            sl_price = entry_price * (1 - Config.SL_PCT) if side == 'LONG' else entry_price * (1 + Config.SL_PCT)
            
            self.positions[strategy_id] = {
                'entry': entry_price,
                'side': side,
                'sl': sl_price,
                'peak': entry_price, 
                'entry_time': time_idx,
                'trailing_active': False,
                'max_drawdown': 0.0,
                'metadata': metadata or {}
            }

    def gestionar(self, candle, current_timestamp):
        high, low, close = candle['high'], candle['low'], candle['close']
        closed_ids = []

        for strat_id, pos in self.positions.items():
            side = pos['side']
            exit_reason = None
            exit_price = None
            pnl = 0

            if side == 'LONG':
                # SL Fijo
                if low <= pos['sl']:
                    exit_reason = 'STOP_LOSS'
                    exit_price = pos['sl']
                
                # Trailing Perezoso
                if high > pos['peak']: pos['peak'] = high
                profit_pct = (pos['peak'] - pos['entry']) / pos['entry']
                
                if profit_pct >= Config.TP_ACTIVATION:
                    pos['trailing_active'] = True
                
                if pos['trailing_active'] and not exit_reason:
                    stop_dyn = pos['peak'] * (1 - Config.TRAILING_GAP)
                    if low <= stop_dyn:
                        exit_price = stop_dyn
                        exit_reason = 'TRAILING_WIN' if exit_price > pos['entry'] else 'TRAILING_LOSS'
                
                cur_dd = (close - pos['peak']) / pos['peak']

            else: # SHORT
                if high >= pos['sl']:
                    exit_reason = 'STOP_LOSS'
                    exit_price = pos['sl']
                
                if low < pos['peak']: pos['peak'] = low
                profit_pct = (pos['entry'] - pos['peak']) / pos['entry']
                
                if profit_pct >= Config.TP_ACTIVATION:
                    pos['trailing_active'] = True
                    
                if pos['trailing_active'] and not exit_reason:
                    stop_dyn = pos['peak'] * (1 + Config.TRAILING_GAP)
                    if high >= stop_dyn:
                        exit_price = stop_dyn
                        exit_reason = 'TRAILING_WIN' if exit_price < pos['entry'] else 'TRAILING_LOSS'
                
                cur_dd = (pos['peak'] - close) / pos['peak']

            pos['max_drawdown'] = min(pos['max_drawdown'], cur_dd)

            if exit_reason:
                if side == 'LONG': pnl = (exit_price - pos['entry']) / pos['entry']
                else: pnl = (pos['entry'] - exit_price) / pos['entry']

                self.closed_trades.append({
                    'id': strat_id,
                    'side': side,
                    'entry_time': pos['entry_time'],
                    'exit_time': current_timestamp,
                    'pnl_pct': pnl,
                    'reason': exit_reason,
                    'max_drawdown': pos['max_drawdown'],
                    'wait_time_min': pos['metadata'].get('wait_time', 0)
                })
                closed_ids.append(strat_id)

        for cid in closed_ids:
            del self.positions[cid]

# =============================================================================
# 4. ORQUESTADOR STALKER
# =============================================================================
class StalkerAuditor:
    def __init__(self):
        self.loader = DataLoader()
        self.loader.load_all()
        self.exchange = VirtualExchange()
        self.stalking_queue = [] 

    def run(self):
        print(f"\n🚀 INICIANDO SIMULACIÓN FINAL (S/L {Config.SL_PCT*100}%)...")
        
        df_1m = self.loader.dfs['1m']
        start_idx = 100
        
        for i in range(start_idx, len(df_1m)):
            row_1m = df_1m.iloc[i]
            ts = row_1m.name
            
            # 1. Contexto
            ctx = self.loader.get_context(ts)
            if not ctx: continue
            
            # 2. Gestión Operaciones
            self.exchange.gestionar(row_1m, ts)
            
            # 3. Gestión Acechos
            active_stalks = []
            for order in self.stalking_queue:
                elapsed = (ts - order['start_time']).total_seconds() / 60
                
                if elapsed > Config.STALK_TIMEOUT_MIN: continue 
                
                if order['state'] == 'WAITING_ACCEL':
                    slope_5m = abs(ctx['5m']['rsi_slope'])
                    if slope_5m >= Config.RSI_SHAKEOUT_SLOPE:
                        order['state'] = 'TRIGGER_READY'
                        order['shakeout_time'] = ts
                        if order['side'] == 'LONG': order['trigger_price'] = row_1m['high']
                        else: order['trigger_price'] = row_1m['low']
                        active_stalks.append(order)
                    else:
                        active_stalks.append(order)
                        
                elif order['state'] == 'TRIGGER_READY':
                    time_since_shakeout = (ts - order['shakeout_time']).total_seconds() / 60
                    if time_since_shakeout > Config.TRIGGER_TIMEOUT_MIN: continue
                    
                    triggered = False
                    entry_price = 0
                    
                    if order['side'] == 'LONG':
                        if row_1m['high'] > order['trigger_price']:
                            triggered = True
                            entry_price = max(row_1m['open'], order['trigger_price'])
                    else:
                        if row_1m['low'] < order['trigger_price']:
                            triggered = True
                            entry_price = min(row_1m['open'], order['trigger_price'])
                            
                    if triggered:
                        trade_id = f"TRD_{ts.strftime('%Y%m%d%H%M')}"
                        meta = {'wait_time': elapsed}
                        self.exchange.abrir(trade_id, entry_price, order['side'], ts, meta)
                    else:
                        active_stalks.append(order)

            self.stalking_queue = active_stalks

            # 4. Escaneo Nuevas Señales
            if len(self.exchange.positions) == 0:
                signal = self._scan_signal(ctx)
                if signal:
                    slope_5m = abs(ctx['5m']['rsi_slope'])
                    
                    # Si ya viene con fuerza (>2.0), entramos directo
                    if slope_5m >= Config.RSI_SHAKEOUT_SLOPE:
                        trade_id = f"TRD_{ts.strftime('%Y%m%d%H%M')}_DIR"
                        self.exchange.abrir(trade_id, row_1m['close'], signal, ts, {'wait_time': 0})
                    else:
                        # Si es débil, acechamos
                        if not any(o['side'] == signal for o in self.stalking_queue):
                            self.stalking_queue.append({
                                'side': signal,
                                'start_time': ts,
                                'state': 'WAITING_ACCEL',
                                'trigger_price': 0,
                                'shakeout_time': None
                            })

        self._generate_report()

    def _scan_signal(self, ctx):
        h1 = ctx['1h']
        m15 = ctx['15m']
        m5 = ctx['5m']
        m1 = ctx['1m']
        
        zoi_long = (h1['close'] <= h1['bb_low']) or (m15['close'] <= m15['bb_low'])
        zoi_short = (h1['close'] >= h1['bb_up']) or (m15['close'] >= m15['bb_up'])
        
        if zoi_long and m5['rsi'] < 40 and m1['rsi'] < 35: return 'LONG'
        if zoi_short and m5['rsi'] > 60 and m1['rsi'] > 65: return 'SHORT'
        return None

    def _generate_report(self):
        print("\n📝 Generando Reporte Final...")
        data = []
        for t in self.exchange.closed_trades:
            data.append({
                'Trade_ID': t['id'],
                'Side': t['side'],
                'Entry_Time': t['entry_time'],
                'PnL_Pct': round(t['pnl_pct'] * 100, 2),
                'Wait_Time_Min': round(t['wait_time_min'], 1),
                'Exit_Reason': t['reason'],
                'Max_Drawdown': round(t['max_drawdown'] * 100, 2)
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df.to_csv("reporte_forense_final.csv", index=False)
            
            wins = len(df[df['PnL_Pct'] > 0])
            total = len(df)
            wr = (wins/total)*100
            gross_pnl = df['PnL_Pct'].sum()
            
            print(f"✅ Reporte guardado: reporte_forense_final.csv")
            print(f"📊 Total Operaciones: {total}")
            print(f"🏆 Win Rate: {wr:.2f}%")
            print(f"💰 PnL Neto Acumulado: {gross_pnl:.2f}%")
            print(f"📉 S/L Usado: {Config.SL_PCT*100}%")
        else:
            print("⚠️ Sin operaciones.")

if __name__ == "__main__":
    bot = StalkerAuditor()
    bot.run()