# =============================================================================
# NOMBRE DEL ARCHIVO: Forensic_Sentinel_Auditor_FINAL.py
# VERSIÓN: 2.0 (Auditada y Calibrada)
# DESCRIPCIÓN: Simulador forense con Gatillo Inteligente, Filtro de Pendiente RSI
# y Trailing Stop dinámico. Genera reporte CSV detallado para validación.
# =============================================================================

import pandas as pd
import numpy as np
import os
import sys
from collections import deque
from datetime import datetime
from scipy.stats import linregress

# =============================================================================
# 1. CONFIGURACIÓN Y PARÁMETROS (CALIBRACIÓN FINAL)
# =============================================================================
class Config:
    # Rutas de datos
    DATA_DIR = "data/historical"
    FILES = {
        '1h': "AAVEUSDT_1h.csv",
        '15m': "AAVEUSDT_15m.csv",
        '5m': "AAVEUSDT_5m.csv",
        '1m': "AAVEUSDT_1m.csv"
    }
    
    # --- PARÁMETROS DE GESTIÓN DE RIESGO ---
    SL_PCT = 0.029            # Stop Loss Fijo: 2.5% (Autorizado)
    TP_ACTIVATION = 0.015     # Activar Trailing solo después de +1.5% de ganancia
    TRAILING_GAP = 0.010      # Distancia del Trailing una vez activado (1%)
    
    # --- PARÁMETROS DE ESTRATEGIA ---
    BB_DEV = 2.0
    RSI_SLOPE_THRESHOLD = 0.5 # Pendiente mínima para entrar "A Mercado"
    
    # --- PARÁMETROS FORENSES ---
    AUDIT_LOOKBACK = 5        # Intervalos previos a guardar
    DRAWDOWN_TRIGGER = 0.01   # Grabar evento si retroceso > 1%

# =============================================================================
# 2. MOTOR SAI (ExhaustionEngine)
# =============================================================================
class ExhaustionEngine:
    def __init__(self):
        self.WEIGHTS = {'rsi': 35, 'adx': 25, 'volume': 20, 'stoch': 20}
        self.THRESHOLDS = {'CRITICAL': 75, 'CAUTION': 35}

    def analyze(self, row, prev_row):
        score_bull = 0 
        score_bear = 0 
        factors = []

        # 1. RSI
        rsi = row.get('rsi', 50)
        if pd.isna(rsi): rsi = 50
        if rsi > 70: score_bear += self.WEIGHTS['rsi']
        if rsi < 30: score_bull += self.WEIGHTS['rsi']

        # 2. ADX
        adx = row.get('adx', 0)
        if pd.isna(adx): adx = 0
        if adx > 40:
            score_bear += self.WEIGHTS['adx']
            score_bull += self.WEIGHTS['adx']

        # 3. Volumen
        vol_curr = row.get('volume', 0)
        vol_prev = prev_row.get('volume', 0)
        if pd.isna(vol_curr): vol_curr = 0
        if pd.isna(vol_prev): vol_prev = 0
        
        if vol_curr < vol_prev:
            score_bear += self.WEIGHTS['volume']
            score_bull += self.WEIGHTS['volume']

        # Nivel
        level_bull = 'SAFE'
        level_bear = 'SAFE'
        
        if score_bull >= self.THRESHOLDS['CAUTION']: level_bull = 'CAUTION'
        if score_bull >= self.THRESHOLDS['CRITICAL']: level_bull = 'CRITICAL'
        if score_bear >= self.THRESHOLDS['CAUTION']: level_bear = 'CAUTION'
        if score_bear >= self.THRESHOLDS['CRITICAL']: level_bear = 'CRITICAL'

        return {
            'bull_level': level_bull,
            'bear_level': level_bear
        }

# =============================================================================
# 3. GESTIÓN DE ORDENES (Exchange Virtual Mejorado)
# =============================================================================
class VirtualExchangeSAI:
    def __init__(self):
        self.positions = {} 
        self.closed_trades = []
        # Trailing perezoso
        self.activation_threshold = Config.TP_ACTIVATION
        self.trailing_gap = Config.TRAILING_GAP

    def abrir(self, strategy_id, entry_price, side, time_idx):
        if strategy_id not in self.positions:
            # Calcular Stop Loss Fijo Inicial (2.5%)
            if side == 'LONG':
                sl_price = entry_price * (1 - Config.SL_PCT)
            else:
                sl_price = entry_price * (1 + Config.SL_PCT)
                
            self.positions[strategy_id] = {
                'entry': entry_price,
                'side': side,
                'sl': sl_price,
                'peak': entry_price, 
                'entry_time': time_idx,
                'trailing_active': False, # Nuevo estado
                'max_drawdown': 0.0, 
                'forensic_events': [] 
            }
            return self.positions[strategy_id]

    def gestionar(self, candle, current_timestamp):
        high, low, close = candle['high'], candle['low'], candle['close']
        closed_ids = []

        for strat_id, pos in self.positions.items():
            side = pos['side']
            exit_reason = None
            exit_price = None
            pnl = 0

            # --- Lógica de Salida ---
            if side == 'LONG':
                # 1. Stop Loss Fijo (Siempre activo por seguridad)
                if low <= pos['sl']:
                    exit_reason = 'STOP_LOSS'
                    exit_price = pos['sl']
                
                # 2. Gestión de Trailing "Perezoso"
                # Solo actualizamos el pico si supera el precio de entrada
                if high > pos['peak']: pos['peak'] = high
                
                # Verificamos si activamos el trailing (Ganancia > 1.5%)
                profit_pct = (pos['peak'] - pos['entry']) / pos['entry']
                
                if profit_pct >= self.activation_threshold:
                    pos['trailing_active'] = True
                
                if pos['trailing_active'] and not exit_reason:
                    dynamic_stop = pos['peak'] * (1 - self.trailing_gap)
                    # Si el precio baja al stop dinámico
                    if low <= dynamic_stop:
                        exit_price = dynamic_stop
                        exit_reason = 'TRAILING_WIN' if exit_price > pos['entry'] else 'TRAILING_LOSS'
                
                # Métrica Forense
                current_dd = (close - pos['peak']) / pos['peak']

            elif side == 'SHORT':
                if high >= pos['sl']:
                    exit_reason = 'STOP_LOSS'
                    exit_price = pos['sl']
                
                if low < pos['peak']: pos['peak'] = low
                
                profit_pct = (pos['entry'] - pos['peak']) / pos['entry']
                
                if profit_pct >= self.activation_threshold:
                    pos['trailing_active'] = True
                    
                if pos['trailing_active'] and not exit_reason:
                    dynamic_stop = pos['peak'] * (1 + self.trailing_gap)
                    if high >= dynamic_stop:
                        exit_price = dynamic_stop
                        exit_reason = 'TRAILING_WIN' if exit_price < pos['entry'] else 'TRAILING_LOSS'
                
                current_dd = (pos['peak'] - close) / pos['peak']

            pos['max_drawdown'] = min(pos['max_drawdown'], current_dd)

            # Cierre y Registro
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
                    'forensic_events': pos['forensic_events']
                })
                closed_ids.append(strat_id)

        for cid in closed_ids:
            del self.positions[cid]

        return closed_ids

# =============================================================================
# 4. CARGADOR DE DATOS
# =============================================================================
class MultiTimeframeLoader:
    def __init__(self):
        self.dfs = {}
        
    def load_data(self):
        print("📂 Cargando datasets...")
        for tf, filename in Config.FILES.items():
            path = os.path.join(Config.DATA_DIR, filename)
            if not os.path.exists(path): path = filename # Fallback local
            
            if os.path.exists(path):
                df = pd.read_csv(path)
                # Detección automática de timestamps
                if 'timestamp' in df.columns:
                    if df['timestamp'].iloc[0] > 10000000000: 
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    else:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                else:
                    df.index = pd.to_datetime(df.index)
                
                self._ensure_indicators(df)
                self.dfs[tf] = df.sort_index()
                print(f"✅ {tf}: {len(df)} registros.")
            else:
                print(f"❌ Error: Falta {filename}")
                sys.exit(1)

    def _ensure_indicators(self, df):
        cols = ['open', 'high', 'low', 'close', 'volume']
        for c in cols:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce')
        
        # Recalcular BB y RSI para asegurar consistencia
        df['bb_middle'] = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (Config.BB_DEV * std)
        df['bb_lower'] = df['bb_middle'] - (Config.BB_DEV * std)
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        df.fillna(method='bfill', inplace=True)

    def get_context(self, timestamp):
        ctx = {}
        for tf in ['1h', '15m', '5m']:
            idx = self.dfs[tf].index.asof(timestamp)
            if pd.isna(idx): return None 
            ctx[tf] = self.dfs[tf].loc[idx]
        return ctx

# =============================================================================
# 5. ORQUESTADOR FORENSE (LÓGICA ACTUALIZADA)
# =============================================================================
class ForensicAuditor:
    def __init__(self):
        self.loader = MultiTimeframeLoader()
        self.loader.load_data()
        self.sai = ExhaustionEngine()
        self.exchange = VirtualExchangeSAI()
        self.history_buffer = deque(maxlen=Config.AUDIT_LOOKBACK) 
    
    def safe_bb_pos(self, row):
        try:
            denom = row['bb_upper'] - row['bb_lower']
            if abs(denom) < 1e-9: return 0.5
            return (row['close'] - row['bb_lower']) / denom
        except: return 0.5

    def get_rsi_slope(self):
        # Calcula pendiente de los últimos 5 RSI en el buffer
        if len(self.history_buffer) < 5: return 0
        y = [snap['rsi_m5'] for snap in self.history_buffer]
        x = range(len(y))
        slope, _, _, _, _ = linregress(x, y)
        return slope

    def run(self):
        print("\n🚀 INICIANDO AUDITORÍA FINAL (Gatillo Inteligente + SL 2.5%)...")
        df_1m = self.loader.dfs['1m']
        price_1m_lookup = df_1m # Copia para acceso rápido por índice
        
        start_idx = 100
        # Loop principal (Vela a Vela)
        # Usamos índice numérico para poder "mirar al futuro" (Gatillo)
        
        i = start_idx
        while i < len(df_1m) - 5: # -5 margen final
            row_1m = df_1m.iloc[i]
            ts = row_1m.name
            
            # 1. Obtener Contexto
            ctx = self.loader.get_context(ts)
            if not ctx: 
                i += 1
                continue
            
            row_h1 = ctx['1h']
            row_m15 = ctx['15m']
            row_m5 = ctx['5m']
            
            # 2. Buffer Forense
            snapshot = {
                'ts': ts,
                'price': row_1m['close'],
                'rsi_m1': row_1m.get('rsi', 50),
                'rsi_m5': row_m5.get('rsi', 50),
                'rsi_m15': row_m15.get('rsi', 50),
                'bb_pos_h1': self.safe_bb_pos(row_h1),
                'bb_pos_m15': self.safe_bb_pos(row_m15),
            }
            self.history_buffer.append(snapshot)
            
            # 3. Detectar Drawdowns
            for strat_id, pos in self.exchange.positions.items():
                current_pnl = (row_1m['close'] - pos['peak'])/pos['peak'] if pos['side'] == 'LONG' else (pos['peak'] - row_1m['close'])/pos['peak']
                
                if current_pnl < -Config.DRAWDOWN_TRIGGER:
                    prev_evts = [e for e in pos['forensic_events'] if e.get('type') == 'DRAWDOWN_ALERT']
                    last_depth = prev_evts[-1]['depth'] if prev_evts else 0
                    if abs(current_pnl - last_depth) > 0.005: 
                        pos['forensic_events'].append({
                            'type': 'DRAWDOWN_ALERT',
                            'timestamp': ts,
                            'depth': current_pnl,
                            'history_pre_event': list(self.history_buffer)
                        })

            # 4. Gestión Salidas
            self.exchange.gestionar(row_1m, ts)
            
            # 5. LÓGICA DE ENTRADA (MODIFICADA)
            if len(self.exchange.positions) == 0:
                base_signal = self._check_base_signal(row_h1, row_m15, row_m5, row_1m)
                
                if base_signal:
                    slope = self.get_rsi_slope()
                    entry_approved = False
                    entry_price = 0
                    entry_time = ts
                    
                    # --- REGLA A: Filtro Anti-Euforia ---
                    # Si el RSI está pegado en extremos (0 o 100) y la pendiente es plana
                    if abs(slope) < 0.1 and (row_m5.get('rsi', 50) > 95 or row_m5.get('rsi', 50) < 5):
                        # Bloqueo total (Trampa detectada)
                        entry_approved = False
                    
                    # --- REGLA B: Gatillo Inteligente ---
                    else:
                        # Opción 1: Pendiente Fuerte -> Entrada Inmediata
                        if abs(slope) >= Config.RSI_SLOPE_THRESHOLD:
                            entry_approved = True
                            entry_price = row_1m['close']
                        
                        # Opción 2: Pendiente Débil -> Esperar Confirmación (2 velas)
                        else:
                            # Miramos al futuro (t+1, t+2)
                            next_1 = df_1m.iloc[i+1]
                            next_2 = df_1m.iloc[i+2]
                            
                            trigger_met = False
                            trigger_price = 0
                            
                            if base_signal == 'LONG':
                                # Debe romper el High de la vela señal (t)
                                ref_price = row_1m['high']
                                if next_1['high'] > ref_price:
                                    trigger_met = True
                                    trigger_price = max(next_1['open'], ref_price) # Simulamos precio de ruptura
                                    # Ajustamos tiempo de entrada simulado
                                    # Nota: Mantenemos el buffer original de la señal para auditoría
                                    entry_time = next_1.name 
                                    i += 1 # Saltamos índice en el loop principal para sincronizar
                                elif next_2['high'] > ref_price:
                                    trigger_met = True
                                    trigger_price = max(next_2['open'], ref_price)
                                    entry_time = next_2.name
                                    i += 2
                            else: # SHORT
                                # Debe romper el Low de la vela señal (t)
                                ref_price = row_1m['low']
                                if next_1['low'] < ref_price:
                                    trigger_met = True
                                    trigger_price = min(next_1['open'], ref_price)
                                    entry_time = next_1.name
                                    i += 1
                                elif next_2['low'] < ref_price:
                                    trigger_met = True
                                    trigger_price = min(next_2['open'], ref_price)
                                    entry_time = next_2.name
                                    i += 2
                                    
                            if trigger_met:
                                entry_approved = True
                                entry_price = trigger_price

                    # Ejecución Final
                    if entry_approved:
                        trade_id = f"TRD_{entry_time.strftime('%Y%m%d%H%M')}"
                        pre_entry_history = list(self.history_buffer) # Guardamos estado de la señal original
                        
                        pos = self.exchange.abrir(trade_id, entry_price, base_signal, entry_time)
                        pos['forensic_events'].append({
                            'type': 'ENTRY_SNAPSHOT',
                            'timestamp': entry_time,
                            'history_pre_event': pre_entry_history
                        })
            
            i += 1 # Avanzar iterador

        self._generate_report()

    def _check_base_signal(self, h1, m15, m5, m1):
        # 1. Zona de Interés (ZOI)
        zoi_long = (h1['close'] <= h1['bb_lower']) or (m15['close'] <= m15['bb_lower'])
        zoi_short = (h1['close'] >= h1['bb_upper']) or (m15['close'] >= m15['bb_upper'])
        
        if not (zoi_long or zoi_short): return None
            
        # 2. Filtro SAI M5
        sai_result = self.sai.analyze(m5, m5) 
        valid_long = False
        valid_short = False
        
        rsi_val = m5.get('rsi', 50)
        
        # Filtro de "Tierra de Nadie" (BB Pos entre 0.4 y 0.6) - Implícito en ZOI (requiere tocar banda)
        # Reforzamos:
        
        if zoi_long:
            if rsi_val < 40 or sai_result['bull_level'] in ['CAUTION', 'CRITICAL']:
                valid_long = True
                
        if zoi_short:
            if rsi_val > 60 or sai_result['bear_level'] in ['CAUTION', 'CRITICAL']:
                valid_short = True
        
        # 3. Gatillo Base M1
        if valid_long and m1.get('rsi', 50) < 35: return 'LONG'
        if valid_short and m1.get('rsi', 50) > 65: return 'SHORT'
                
        return None

    def _generate_report(self):
        print("\n📝 Generando Reporte Final 'reporte_forense_auditor.csv'...")
        data = []
        
        for t in self.exchange.closed_trades:
            row = {
                'Trade_ID': t['id'],
                'Side': t['side'],
                'Entry_Time': t['entry_time'],
                'Exit_Time': t['exit_time'],
                'PnL_Pct': round(t['pnl_pct'] * 100, 2),
                'Max_Drawdown': round(t['max_drawdown'] * 100, 2),
                'Exit_Reason': t['reason']
            }
            
            # Datos de Entrada
            entry_event = next((e for e in t['forensic_events'] if e['type'] == 'ENTRY_SNAPSHOT'), None)
            if entry_event:
                hist = entry_event['history_pre_event']
                for i, snapshot in enumerate(reversed(hist)): 
                    idx = i + 1
                    row[f'Pre_Entry_{idx}_RSI_M5'] = snapshot['rsi_m5']
                    row[f'Pre_Entry_{idx}_BB_Pos_H1'] = snapshot['bb_pos_h1']
            
            # Datos de Drawdown
            dd_events = [e for e in t['forensic_events'] if e['type'] == 'DRAWDOWN_ALERT']
            if dd_events:
                worst_dd = min(dd_events, key=lambda x: x['depth'])
                row['Has_Severe_DD'] = True
                row['DD_Depth'] = worst_dd['depth']
                
                for i, snapshot in enumerate(reversed(worst_dd['history_pre_event'])):
                    idx = i + 1
                    row[f'Pre_Crash_{idx}_RSI_M5'] = snapshot['rsi_m5']
            else:
                row['Has_Severe_DD'] = False
                row['DD_Depth'] = 0

            data.append(row)
            
        df = pd.DataFrame(data)
        if not df.empty:
            df.to_csv("reporte_forense_auditor.csv", index=False)
            print(f"✅ Reporte guardado con Éxito.")
            print(f"📊 Total Operaciones: {len(df)}")
            wins = len(df[df['PnL_Pct'] > 0])
            print(f"🏆 Ganadoras: {wins} ({wins/len(df)*100:.1f}%)")
            print(f"📉 Drawdowns Severos (>1%): {df['Has_Severe_DD'].sum()}")
        else:
            print("⚠️ No se generaron operaciones.")

if __name__ == "__main__":
    auditor = ForensicAuditor()
    auditor.run()