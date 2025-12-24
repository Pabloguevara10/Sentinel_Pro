import pandas as pd
import numpy as np
import os
import sys
import time
from datetime import datetime

# Ajuste de rutas
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.config import Config
from tools.precision_lab import PrecisionLab
from logic.brain import Brain
from logic.shooter import Shooter
from data.calculator import Calculator

class BacktesterSwing:
    """
    SIMULADOR SWING V1.2 (Gestión Pro):
    - Stop Loss: 1.5%
    - Break Even: Activa al 2% -> Mueve a +0.5%
    - TP1: 5% -> Cierra 50%
    - Resto: Trailing Stop Dinámico (Smart Exit)
    """
    def __init__(self):
        print("\n🦅 LABORATORIO SWING V1.2 (GESTIÓN PRO)...")
        self.cfg = Config()
        self.lab = PrecisionLab()
        self.brain = Brain(self.cfg)
        
        class DummyLogger:
            def registrar_actividad(self, a, b): pass
        self.shooter = Shooter(self.cfg, DummyLogger())
        
        self.capital = 1000.0
        self.trades_log = []
        self.data_cache = {}
        self.report_dir = current_dir

    def cargar_datos(self):
        print("📂 Cargando Data Swing (4h, 15m, 1m)...")
        for tf in ['1m', '15m', '4h']:
            path = os.path.join(self.cfg.DIR_DATA, f"{self.cfg.SYMBOL}_{tf}.csv")
            if not os.path.exists(path):
                print(f"❌ Falta archivo: {path}")
                return False
            try:
                df = pd.read_csv(path)
                if 'ts' in df.columns: df.rename(columns={'ts': 'timestamp'}, inplace=True)
                df = Calculator.calcular_indicadores(df)
                self.data_cache[tf] = df
            except Exception as e:
                print(f"❌ Error leyendo {tf}: {e}")
                return False
        return True

    def ejecutar_simulacion(self):
        if not self.cargar_datos(): return

        df_1m = self.data_cache['1m']
        df_15m = self.data_cache['15m']
        df_4h = self.data_cache['4h']
        
        start_ts = max(df_1m.iloc[0]['timestamp'], df_15m.iloc[0]['timestamp'], df_4h.iloc[0]['timestamp'])
        print(f"📅 Inicio Sincronizado: {datetime.fromtimestamp(start_ts/1000)}")
        
        start_idx = df_15m[df_15m['timestamp'] >= start_ts].index[0]
        start_idx = max(start_idx, 200)
        
        total = len(df_15m)
        print(f"🚀 Iniciando recorrido de {total - start_idx} velas de 15m...")
        
        posicion = None
        
        for i in range(start_idx, total - 1):
            curr_candle = df_15m.iloc[i]
            curr_ts = curr_candle['timestamp']
            
            # GESTIÓN (Usando data de 1m)
            if posicion:
                self._gestionar_posicion(posicion, curr_ts, df_1m)
                if posicion['estado'] == 'CERRADA':
                    self.trades_log.append(posicion)
                    posicion = None
            
            # ENTRADA
            if not posicion:
                slice_macro = df_4h[df_4h['timestamp'] <= curr_ts].iloc[-100:]
                slice_micro = df_15m.iloc[i-100 : i+1]
                
                brain_cache = {'1h': slice_macro, '5m': slice_micro}
                signal = self.brain.analizar_mercado(brain_cache)
                
                if signal:
                    signal['strategy'] = 'SWING_4H_PRO'
                    plan = self.shooter.validar_y_crear_plan(signal, 0)
                    if plan:
                        posicion = self._iniciar_trade(plan, curr_candle, df_1m)

            if i % 500 == 0:
                sys.stdout.write(f"\r   ⏳ Progreso: {i}/{total}...")
                sys.stdout.flush()

        print("\n✅ Simulación Swing Finalizada.")
        self._generar_reporte()

    def _iniciar_trade(self, plan, candle, df_1m):
        entry_ts = candle['timestamp']
        subset = df_1m[df_1m['timestamp'] <= entry_ts]
        if subset.empty: return None
        
        entry_price = plan['entry_price']
        side = plan['side']
        
        # --- REGLA 1: STOP LOSS AL 1.5% ---
        sl_pct = 0.015
        if side == 'LONG':
            sl_price = entry_price * (1 - sl_pct)
        else:
            sl_price = entry_price * (1 + sl_pct)
            
        # --- REGLA 3: TP1 AL 5% ---
        tp1_pct = 0.05
        if side == 'LONG':
            tp1_price = entry_price * (1 + tp1_pct)
        else:
            tp1_price = entry_price * (1 - tp1_pct)

        # Radiografía
        idx = subset.index[-1]
        radio_data = df_1m.iloc[max(0, idx-5):idx]
        radiografia = " || ".join([f"RSI:{r.get('rsi',0):.0f}" for _, r in radio_data.iterrows()])

        return {
            'id': len(self.trades_log) + 1,
            'fecha': datetime.fromtimestamp(entry_ts/1000).strftime('%Y-%m-%d %H:%M'),
            'ts_entry': entry_ts,
            'last_check_ts': entry_ts,
            'strategy': plan['strategy'],
            'side': side,
            'entry': entry_price,
            'qty': plan['qty'], # Qty inicial calculada por shooter (ajustar si se quiere riesgo fijo 1.5%)
            # Si Shooter usó 5% riesgo, con SL 1.5% el lotaje sería mayor. 
            # Para esta simulación usaremos el qty del shooter pero aplicaremos las salidas nuevas.
            
            'sl_current': sl_price,
            'tp1': tp1_price,
            
            'estado': 'ABIERTA',
            'resultado': 'PENDIENTE',
            'pnl': 0.0, # PnL acumulado (realizado)
            'tp_level': 0,
            'be_active': False,
            'radiografia': radiografia
        }

    def _gestionar_posicion(self, trade, limit_ts, df_1m):
        candles = df_1m[(df_1m['timestamp'] > trade['last_check_ts']) & (df_1m['timestamp'] <= limit_ts)]
        if candles.empty:
            trade['last_check_ts'] = limit_ts
            return

        side = trade['side']
        entry = trade['entry']
        
        for _, row in candles.iterrows():
            high, low, close = row['high'], row['low'], row['close']
            
            # 1. STOP LOSS CHECK
            sl_hit = (side == 'LONG' and low <= trade['sl_current']) or \
                     (side == 'SHORT' and high >= trade['sl_current'])
            
            if sl_hit:
                reason = 'STOP_LOSS'
                if trade['be_active']: reason = 'PROFIT_PROTEGIDO'
                if trade['tp_level'] >= 1: reason = 'TRAILING_STOP'
                
                self._cerrar(trade, trade['sl_current'], reason)
                return

            # 2. GESTIÓN BREAK EVEN (+0.5% Gananacia al cruzar 2%)
            roi = (high - entry)/entry if side == 'LONG' else (entry - low)/entry
            
            if not trade['be_active'] and roi >= 0.02:
                trade['be_active'] = True
                # Aseguramos 0.5% de ganancia mínima
                if side == 'LONG':
                    trade['sl_current'] = entry * 1.005 
                else:
                    trade['sl_current'] = entry * 0.995

            # 3. GESTIÓN TP1 (5%) -> VENTA PARCIAL 50%
            if trade['tp_level'] < 1:
                tp_hit = (side == 'LONG' and high >= trade['tp1']) or (side == 'SHORT' and low <= trade['tp1'])
                
                if tp_hit:
                    trade['tp_level'] = 1
                    trade['be_active'] = True # Aseguramos BE por si acaso
                    
                    # Ejecutar Parcial
                    qty_sold = trade['qty'] * 0.50
                    price_sold = trade['tp1']
                    
                    gain = (price_sold - entry) * qty_sold if side == 'LONG' else (entry - price_sold) * qty_sold
                    
                    trade['pnl'] += gain
                    self.capital += gain # Sumar a la caja
                    trade['qty'] -= qty_sold # Reducir posición
                    
                    # Subir SL al precio de entrada o dejarlo en +0.5% (ya está en +0.5% por la regla 2)

            # 4. GESTIÓN TRAILING (Para el 50% restante)
            if trade['tp_level'] >= 1:
                # Usamos lógica Smart Exit V12
                adx = row.get('adx', 0)
                rsi = row.get('rsi', 50)
                
                rsi_extremo = rsi > 80 if side == 'LONG' else rsi < 20
                dist = 0.01 if rsi_extremo else 0.03 # 3% de aire para Swing
                
                if side == 'LONG':
                    new_sl = close * (1 - dist)
                    if new_sl > trade['sl_current']: trade['sl_current'] = new_sl
                else:
                    new_sl = close * (1 + dist)
                    if new_sl < trade['sl_current']: trade['sl_current'] = new_sl

        trade['last_check_ts'] = limit_ts

    def _cerrar(self, trade, price, reason):
        trade['estado'] = 'CERRADA'
        trade['resultado'] = reason
        trade['precio_salida'] = price
        
        # Calcular PnL del remanente
        diff = (price - trade['entry']) if trade['side'] == 'LONG' else (trade['entry'] - price)
        pnl_remanente = diff * trade['qty']
        
        trade['pnl'] += pnl_remanente
        self.capital += pnl_remanente

    def _generar_reporte(self):
        path = os.path.join(self.report_dir, 'reporte_swing_v1.2.csv')
        if not self.trades_log:
            print("\n⚠️ Sin operaciones Swing.")
            return
        
        df = pd.DataFrame(self.trades_log)
        wins = len(df[df['pnl'] > 0])
        print(f"\n📊 RESULTADOS SWING V1.2")
        print(f"   Ops: {len(df)} | Wins: {wins}")
        print(f"   Win Rate: {(wins/len(df))*100:.1f}%")
        print(f"   Capital Final: ${self.capital:.2f}")
        
        cols = ['id','fecha','strategy','side','entry','precio_salida','resultado','pnl','tp_level']
        final_cols = [c for c in cols if c in df.columns]
        df[final_cols].to_csv(path, index=False)
        print(f"   Reporte guardado en: {path}")

if __name__ == "__main__":
    sim = BacktesterSwing()
    sim.ejecutar_simulacion()