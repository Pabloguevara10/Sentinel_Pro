# =============================================================================
# NOMBRE: SwingHunter_Alpha.py (Versión 3.0 - Fractional Logic)
# UBICACIÓN: tests/SwingHunter_Alpha.py
# DESCRIPCIÓN: 
#   Estrategia Swing con Salidas Parciales (Fractional TP).
#   - SL Ampliado: 6.0%
#   - TP1: 30% a +6% (Move to BE)
#   - TP2: 30% a +12%
#   - TP3: 40% Runner (Trailing Dinámico)
# =============================================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# --- 1. CONFIGURACIÓN DE RUTAS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
tools_path = os.path.join(project_root, 'tools')
sys.path.append(tools_path)

try:
    from StructureScanner import StructureScanner
    from Reporter import TradingReporter
    print("✅ Herramientas cargadas correctamente (Swing V3 Fractional).")
except ImportError as e:
    print(f"❌ Error Crítico: {e}")
    sys.exit(1)

# =============================================================================
# 2. CONFIGURACIÓN SWING V3
# =============================================================================
class Config:
    # Rutas (Nativas)
    FILE_1D = "../data/historical/AAVEUSDT_1d.csv"   
    FILE_4H = "../data/historical/AAVEUSDT_4h.csv"   
    FILE_1H = "../data/historical/AAVEUSDT_1h.csv"   
    
    RSI_PERIOD = 14
    
    # --- FILTROS DE ENTRADA (Mismos que V2) ---
    FILTRO_DIST_FIBO_MACRO = 0.025 
    FILTRO_MACD_1H_MIN = 0.0       
    
    HEDGE_DIST_FIBO_MIN = 0.050    
    HEDGE_MACD_1H_MAX = -0.05      
    
    # --- GESTIÓN DE SALIDA (FRACCIONADA) ---
    # STOP LOSS INICIAL
    SL_INITIAL_NORMAL = 0.060  # 6.0% (Ampliado para evitar barridas)
    SL_INITIAL_HEDGE = 0.030   # 3.0% (Más ajustado en contra-tendencia)
    
    # TARGETS NORMAL (Escalera)
    TP1_DIST_NORMAL = 0.06     # +6%
    TP1_QTY_NORMAL = 0.30      # Vender 30%
    
    TP2_DIST_NORMAL = 0.12     # +12%
    TP2_QTY_NORMAL = 0.30      # Vender 30%
    
    # RUNNER (El 40% restante usa Trailing)
    RUNNER_TRAILING_START = 0.15 # Activar trailing fuerte al 15%
    RUNNER_TRAILING_GAP = 0.03   # Mantener distancia del 3%

    # TARGETS HEDGE (Simples, porque es reversión)
    TP_HEDGE_FULL = 0.08       # 8% (Salida completa)

# =============================================================================
# 3. UTILIDADES
# =============================================================================
class DataProcessor:
    @staticmethod
    def add_indicators(df):
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(Config.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(Config.RSI_PERIOD).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        k_fast = df['close'].ewm(span=12).mean()
        k_slow = df['close'].ewm(span=26).mean()
        macd_line = k_fast - k_slow
        macd_signal = macd_line.ewm(span=9).mean()
        df['macd_hist'] = macd_line - macd_signal
        return df

# =============================================================================
# 4. CEREBRO SWING
# =============================================================================
class SwingBrain:
    def get_raw_signal(self, row):
        if row['rsi'] < 35: return 'LONG_INTENT'
        if row['rsi'] > 65: return 'SHORT_INTENT'
        return None

# =============================================================================
# 5. MOTOR PRINCIPAL (CON GESTIÓN FRACCIONADA)
# =============================================================================
class SwingHunterAlpha:
    def __init__(self):
        self.brain = SwingBrain()
        self.reporter = TradingReporter("SwingHunter_V3_Fractional", initial_capital=1000)
        self.positions = [] 
        
        print("\n🔎 CARGANDO DATOS V3 (Fractional Logic)...")
        path_1d = os.path.join(os.path.dirname(__file__), Config.FILE_1D)
        path_4h = os.path.join(os.path.dirname(__file__), Config.FILE_4H)
        path_1h = os.path.join(os.path.dirname(__file__), Config.FILE_1H)
        
        self.df_1d = self._load_csv(path_1d)
        self.df_4h = self._load_csv(path_4h)
        self.df_1h = self._load_csv(path_1h)
        
        # Scanners
        if not self.df_1d.empty:
            self.df_1d = DataProcessor.add_indicators(self.df_1d)
            self.scanner_1d = StructureScanner(self.df_1d)
            self.scanner_1d.precompute()
        if not self.df_4h.empty:
            self.df_4h = DataProcessor.add_indicators(self.df_4h)
            self.scanner_4h = StructureScanner(self.df_4h)
            self.scanner_4h.precompute()
        if not self.df_1h.empty:
            self.df_1h = DataProcessor.add_indicators(self.df_1h)

    def _load_csv(self, filepath):
        if not os.path.exists(filepath): return pd.DataFrame()
        try:
            df = pd.read_csv(filepath)
            df.columns = [c.lower().strip() for c in df.columns]
            cols = ['open', 'high', 'low', 'close', 'volume']
            for c in cols: df[c] = pd.to_numeric(df[c], errors='coerce')
            
            if 'timestamp' in df.columns:
                if df['timestamp'].iloc[0] > 10000000000: 
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            return df.dropna()
        except Exception:
            return pd.DataFrame()

    def get_context_dist(self, ts):
        # Distancia 1D
        dist_1d = 999
        idx_1d = self.df_1d.index.get_indexer([ts], method='pad')[0]
        if idx_1d != -1:
            ctx = self.scanner_1d.get_fibonacci_context(idx_1d)
            if ctx:
                price = self.df_1d.iloc[idx_1d]['close']
                for lvl in ctx['fibs'].values():
                    d = abs(price - lvl) / price
                    if d < dist_1d: dist_1d = d
        
        # Distancia 4H
        dist_4h = 999
        idx_4h = self.df_4h.index.get_indexer([ts], method='pad')[0]
        if idx_4h != -1:
            ctx = self.scanner_4h.get_fibonacci_context(idx_4h)
            if ctx:
                price = self.df_4h.iloc[idx_4h]['close']
                for lvl in ctx['fibs'].values():
                    d = abs(price - lvl) / price
                    if d < dist_4h: dist_4h = d
        
        return min(dist_1d, dist_4h)

    def run_simulation(self):
        if self.df_1h.empty: return
        print("\n🚀 Iniciando Simulación V3...")
        
        for i in range(50, len(self.df_1h)):
            row_1h = self.df_1h.iloc[i]
            ts = row_1h.name
            
            # 1. GESTIÓN
            active_pos = None
            if self.positions:
                active_pos = self.positions[0]
                self._manage_position(active_pos, row_1h)
                if active_pos['status'] == 'CLOSED':
                    self.reporter.add_trade(active_pos)
                    self.positions.clear()
            
            # 2. ENTRADA
            if not active_pos:
                intent = self.brain.get_raw_signal(row_1h)
                if intent:
                    dist_macro = self.get_context_dist(ts)
                    macd_1h = row_1h['macd_hist']
                    
                    final_action = "WAIT"
                    mode = "NONE"
                    
                    # LOGICA DUAL CORE (Igual que V2)
                    if intent == 'LONG_INTENT':
                        if macd_1h > Config.FILTRO_MACD_1H_MIN and dist_macro < Config.FILTRO_DIST_FIBO_MACRO:
                            final_action = "GO_LONG"
                            mode = "SWING_NORMAL"
                        elif macd_1h < Config.HEDGE_MACD_1H_MAX and dist_macro > Config.HEDGE_DIST_FIBO_MIN:
                            final_action = "GO_SHORT"
                            mode = "SWING_HEDGE"
                            
                    elif intent == 'SHORT_INTENT':
                        if macd_1h < -Config.FILTRO_MACD_1H_MIN and dist_macro < Config.FILTRO_DIST_FIBO_MACRO:
                            final_action = "GO_SHORT"
                            mode = "SWING_NORMAL"
                        elif macd_1h > -Config.HEDGE_MACD_1H_MAX and dist_macro > Config.HEDGE_DIST_FIBO_MIN:
                            final_action = "GO_LONG"
                            mode = "SWING_HEDGE"

                    if final_action != "WAIT":
                        entry = row_1h['close']
                        side = 'LONG' if 'LONG' in final_action else 'SHORT'
                        
                        sl_pct = Config.SL_INITIAL_NORMAL if mode == "SWING_NORMAL" else Config.SL_INITIAL_HEDGE
                        sl_price = entry * (1 - sl_pct) if side == 'LONG' else entry * (1 + sl_pct)
                        
                        # Definir TP Final para referencia (aunque usaremos lógica fraccionada)
                        tp_final = entry * (1.20) # 20% referencia
                        
                        self.positions.append({
                            'Trade_ID': f"SW_{ts.strftime('%d%H%M')}",
                            'Strategy': f"Swing_{mode}",
                            'Side': side,
                            'Entry_Time': ts, 'Entry_Price': entry,
                            'Exit_Time': None, 'Exit_Price': None, 'PnL_Pct': 0.0,
                            'Exit_Reason': None,
                            'Structure_Context': f"{mode}|Dist:{dist_macro:.3f}",
                            'Fibo_Target': tp_final,
                            'SL': sl_price,
                            'Peak_Price': entry,
                            'Mode': mode,
                            'Remaining_Qty': 1.0, # 100% de la posición
                            'TP1_Hit': False,
                            'TP2_Hit': False,
                            'status': 'OPEN'
                        })

        self.reporter.generate_report()

    def _manage_position(self, trade, row):
        curr = row['close']
        entry = trade['Entry_Price']
        mode = trade.get('Mode', 'SWING_NORMAL')
        side = trade['Side']
        
        # --- GESTIÓN MODO HEDGE (SIMPLE) ---
        if mode == "SWING_HEDGE":
            tp_price = entry * (1 + Config.TP_HEDGE_FULL) if side == 'LONG' else entry * (1 - Config.TP_HEDGE_FULL)
            
            if side == 'LONG':
                if curr >= tp_price: self._close_trade(trade, curr, row.name, 'TP_HEDGE_FULL')
                elif curr <= trade['SL']: self._close_trade(trade, curr, row.name, 'SL_HEDGE')
            else: # SHORT
                if curr <= tp_price: self._close_trade(trade, curr, row.name, 'TP_HEDGE_FULL')
                elif curr >= trade['SL']: self._close_trade(trade, curr, row.name, 'SL_HEDGE')
            return

        # --- GESTIÓN MODO NORMAL (FRACCIONADA) ---
        # Calcular progreso positivo (Ganancia actual %)
        if side == 'LONG':
            gain_pct = (curr - entry) / entry
            trade['Peak_Price'] = max(trade['Peak_Price'], curr)
            peak_gain = (trade['Peak_Price'] - entry) / entry
            
            # CHECK SL (GLOBAL)
            if curr <= trade['SL']: 
                self._close_trade(trade, curr, row.name, 'SL_HIT_REMAINING')
                return

            # CHECK TP1 (+6%)
            if not trade['TP1_Hit'] and gain_pct >= Config.TP1_DIST_NORMAL:
                trade['TP1_Hit'] = True
                trade['Remaining_Qty'] -= Config.TP1_QTY_NORMAL
                # MOVER SL A BREAK EVEN
                trade['SL'] = entry
                # Aquí deberíamos registrar el cobro parcial en un sistema real.
                # Para simulación simple, asumimos que mejora el PnL promedio.
                
            # CHECK TP2 (+12%)
            if not trade['TP2_Hit'] and gain_pct >= Config.TP2_DIST_NORMAL:
                trade['TP2_Hit'] = True
                trade['Remaining_Qty'] -= Config.TP2_QTY_NORMAL
                # Mover SL a TP1 (Asegurar 6%)
                trade['SL'] = entry * (1 + Config.TP1_DIST_NORMAL)
            
            # CHECK RUNNER TRAILING (Solo si ya pasamos TP2 o estamos muy arriba)
            if trade['TP2_Hit'] or peak_gain > Config.RUNNER_TRAILING_START:
                # Trailing del 3% desde el pico
                dynamic_sl = trade['Peak_Price'] * (1 - Config.RUNNER_TRAILING_GAP)
                if dynamic_sl > trade['SL']: trade['SL'] = dynamic_sl
        
        else: # SHORT
            gain_pct = (entry - curr) / entry
            trade['Peak_Price'] = min(trade['Peak_Price'], curr)
            peak_gain = (entry - trade['Peak_Price']) / entry
            
            if curr >= trade['SL']: 
                self._close_trade(trade, curr, row.name, 'SL_HIT_REMAINING')
                return

            # CHECK TP1
            if not trade['TP1_Hit'] and gain_pct >= Config.TP1_DIST_NORMAL:
                trade['TP1_Hit'] = True
                trade['Remaining_Qty'] -= Config.TP1_QTY_NORMAL
                trade['SL'] = entry # BE
                
            # CHECK TP2
            if not trade['TP2_Hit'] and gain_pct >= Config.TP2_DIST_NORMAL:
                trade['TP2_Hit'] = True
                trade['Remaining_Qty'] -= Config.TP2_QTY_NORMAL
                trade['SL'] = entry * (1 - Config.TP1_DIST_NORMAL) # SL en TP1
            
            # TRAILING
            if trade['TP2_Hit'] or peak_gain > Config.RUNNER_TRAILING_START:
                dynamic_sl = trade['Peak_Price'] * (1 + Config.RUNNER_TRAILING_GAP)
                if dynamic_sl < trade['SL']: trade['SL'] = dynamic_sl

    def _close_trade(self, trade, price, time, reason):
        # CALCULAR PNL PONDERADO
        # Si sacamos parciales, el PnL no es (Salida - Entrada). 
        # Es una suma de las partes.
        # Simplificación para reporte:
        # PnL Total = (TP1_Gain * 0.3) + (TP2_Gain * 0.3) + (Exit_Gain * Remanente)
        
        entry = trade['Entry_Price']
        side = trade['Side']
        
        # Ganancia del tramo final (remanente)
        final_gain_pct = (price - entry)/entry if side == 'LONG' else (entry - price)/entry
        
        pnl_accum = 0.0
        used_qty = 0.0
        
        if trade.get('TP1_Hit'):
            pnl_accum += Config.TP1_DIST_NORMAL * Config.TP1_QTY_NORMAL
            used_qty += Config.TP1_QTY_NORMAL
            
        if trade.get('TP2_Hit'):
            pnl_accum += Config.TP2_DIST_NORMAL * Config.TP2_QTY_NORMAL
            used_qty += Config.TP2_QTY_NORMAL
            
        remaining = 1.0 - used_qty
        pnl_accum += final_gain_pct * remaining
        
        trade['Exit_Price'] = price
        trade['Exit_Time'] = time
        trade['Exit_Reason'] = reason
        trade['status'] = 'CLOSED'
        
        # Si es Hedge, no hay fraccionado, es directo
        if trade.get('Mode') == 'SWING_HEDGE':
             trade['PnL_Pct'] = final_gain_pct
        else:
             trade['PnL_Pct'] = pnl_accum

if __name__ == "__main__":
    bot = SwingHunterAlpha()
    bot.run_simulation()