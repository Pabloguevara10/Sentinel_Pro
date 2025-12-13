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

class BacktesterSniper:
    """
    SIMULADOR SNIPER V12 (Smart Exit):
    - Break Even al 2%
    - TP3 Dinámico basado en ADX/RSI (Modo Surfer)
    """
    def __init__(self):
        print("\n🔬 LABORATORIO SNIPER V12 (SMART EXIT)...")
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
        print("📂 Cargando Data...")
        for tf in ['1m', '5m', '1h']:
            path = os.path.join(self.cfg.DIR_DATA, f"{self.cfg.SYMBOL}_{tf}.csv")
            if not os.path.exists(path): return False
            df = pd.read_csv(path)
            if 'ts' in df.columns: df.rename(columns={'ts': 'timestamp'}, inplace=True)
            df = Calculator.calcular_indicadores(df) # Recalculamos para asegurar ADX
            self.data_cache[tf] = df
        return True

    def ejecutar_simulacion(self):
        if not self.cargar_datos(): return

        df_1m, df_5m, df_1h = self.data_cache['1m'], self.data_cache['5m'], self.data_cache['1h']
        
        # Sincronización
        start_ts = max(df_1m.iloc[0]['timestamp'], df_5m.iloc[0]['timestamp'], df_1h.iloc[0]['timestamp'])
        start_idx = df_5m[df_5m['timestamp'] >= start_ts].index[0]
        start_idx = max(start_idx, 200)
        
        posicion = None
        
        print(f"🚀 Iniciando simulación V12...")
        
        for i in range(start_idx, len(df_5m) - 1):
            curr_candle = df_5m.iloc[i]
            curr_ts = curr_candle['timestamp']
            
            # Gestión
            if posicion:
                self._gestionar_posicion(posicion, curr_ts, df_1m)
                if posicion['estado'] == 'CERRADA':
                    self.trades_log.append(posicion)
                    posicion = None
            
            # Entrada
            if not posicion:
                slice_1h = df_1h[df_1h['timestamp'] <= curr_ts].iloc[-100:]
                slice_5m = df_5m.iloc[i-100 : i+1]
                
                signal = self.brain.analizar_mercado({'1h': slice_1h, '5m': slice_5m})
                if signal:
                    plan = self.shooter.validar_y_crear_plan(signal, 0)
                    if plan:
                        posicion = self._iniciar_trade(plan, curr_candle, df_1m)

            if i % 1000 == 0: sys.stdout.write(f"\r   ⏳ Procesando... {i}")

        self._generar_reporte("reporte_sniper_v12.csv")

    def _iniciar_trade(self, plan, candle, df_1m):
        entry_ts = candle['timestamp']
        # Radiografía simplificada
        return {
            'id': len(self.trades_log) + 1,
            'fecha': datetime.fromtimestamp(entry_ts/1000).strftime('%Y-%m-%d %H:%M'),
            'ts_entry': entry_ts,
            'last_check_ts': entry_ts,
            'side': plan['side'],
            'entry': plan['entry_price'],
            'sl_current': plan['sl_price'],
            'tp1': plan['tps'][0]['price'],
            'tp2': plan['tps'][1]['price'],
            'qty': plan['qty'],
            'estado': 'ABIERTA',
            'resultado': 'PENDIENTE',
            'pnl': 0.0,
            'tp_level': 0,
            'be_active': False
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
            
            # 1. Stop Loss Check
            sl_hit = (side == 'LONG' and low <= trade['sl_current']) or \
                     (side == 'SHORT' and high >= trade['sl_current'])
            if sl_hit:
                self._cerrar(trade, trade['sl_current'], 'STOP_LOSS' if not trade['be_active'] else 'PROTECCION')
                return

            # 2. Break Even al 2% (NUEVA REGLA)
            roi = (high - entry)/entry if side == 'LONG' else (entry - low)/entry
            if not trade['be_active'] and roi >= 0.02:
                trade['be_active'] = True
                trade['sl_current'] = entry * 1.001 if side == 'LONG' else entry * 0.999 # BE + Fees
            
            # 3. TP1 y TP2 (Fijos)
            if trade['tp_level'] < 1:
                hit = (side == 'LONG' and high >= trade['tp1']) or (side == 'SHORT' and low <= trade['tp1'])
                if hit: 
                    trade['tp_level'] = 1
                    trade['be_active'] = True
                    trade['sl_current'] = entry 

            if trade['tp_level'] < 2 and trade['tp_level'] >= 1:
                hit = (side == 'LONG' and high >= trade['tp2']) or (side == 'SHORT' and low <= trade['tp2'])
                if hit:
                    trade['tp_level'] = 2
                    trade['sl_current'] = trade['tp1'] # Asegurar TP1

            # 4. TP3 DINÁMICO (Modo Surfer)
            if trade['tp_level'] >= 2:
                # Monitoreo de Fuerza (ADX + RSI)
                adx = row.get('adx', 0)
                rsi = row.get('rsi', 50)
                
                # Definir Distancia de Trailing según Fuerza
                fuerza_tendencia = adx > 25
                rsi_extremo = rsi > 75 if side == 'LONG' else rsi < 25
                
                if fuerza_tendencia and not rsi_extremo:
                    dist = 0.02 # Dejar correr (2%)
                else:
                    dist = 0.005 # Apretar (0.5%) porque se debilita
                
                # Actualizar SL Dinámico
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
        diff = (price - trade['entry']) if trade['side'] == 'LONG' else (trade['entry'] - price)
        trade['pnl'] = diff * trade['qty']
        self.capital += trade['pnl']

    def _generar_reporte(self, filename):
        path = os.path.join(self.report_dir, filename)
        if not self.trades_log: 
            print("\n⚠️ Sin operaciones.")
            return
        
        df = pd.DataFrame(self.trades_log)
        wins = len(df[df['pnl'] > 0])
        print(f"\n📊 SIMULACIÓN FINALIZADA")
        print(f"   Ops: {len(df)} | Wins: {wins}")
        print(f"   Capital Final: ${self.capital:.2f}")
        df.to_csv(path, index=False)
        print(f"   Reporte en: {path}")

if __name__ == "__main__":
    sim = BacktesterSniper()
    sim.ejecutar_simulacion()