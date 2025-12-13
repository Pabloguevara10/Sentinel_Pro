import pandas as pd
import numpy as np
import os
import sys
import traceback
from datetime import datetime

# Ajuste de rutas
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.config import Config
from tools.precision_lab import PrecisionLab
from tools.smart_money_logic import SmartMoneyLogic
from logic.brain import Brain
from data.calculator import Calculator

class BacktesterSwingATRTest:
    """
    SIMULADOR ATR TEST (Experimento de Volatilidad):
    - Estrategia Base: ALFA2 (Híbrido)
    - Agregado: 'Phantom Tracker' que simula un Trailing Stop de 1.5 ATR
      para verificar si el precio nos hubiera sacado antes.
    """
    def __init__(self):
        print("\n🦅 LABORATORIO ATR TEST (1.5 ATR PHANTOM TRACKER)...")
        self.cfg = Config()
        self.lab = PrecisionLab()
        self.smc = SmartMoneyLogic()
        self.brain = Brain(self.cfg)
        
        self.capital = 1000.0
        self.trades_log = []
        self.data_cache = {}
        self.mapa_4h = [] 
        self.report_dir = current_dir

    def cargar_recursos(self):
        print("📂 Cargando Data (4h, 15m, 1m)...")
        for tf in ['1m', '15m', '4h']:
            path = os.path.join(self.cfg.DIR_DATA, f"{self.cfg.SYMBOL}_{tf}.csv")
            if not os.path.exists(path): return False
            try:
                df = pd.read_csv(path)
                if 'ts' in df.columns: df.rename(columns={'ts': 'timestamp'}, inplace=True)
                # IMPORTANTE: Calculator ya calcula 'atr'
                self.data_cache[tf] = Calculator.calcular_indicadores(df)
            except Exception as e:
                print(f"❌ Error cargando {tf}: {e}")
                return False

        map_path = os.path.join(self.cfg.DIR_DATA, 'mapas_fvg', f"mapa_fvg_4h.csv")
        if not os.path.exists(map_path): return False
        self.mapa_4h = pd.read_csv(map_path).to_dict('records')
        print(f"   ✅ Zonas Cargadas: {len(self.mapa_4h)}")
        return True

    def ejecutar_simulacion(self):
        if not self.cargar_recursos(): return

        df_1m = self.data_cache['1m']
        df_15m = self.data_cache['15m']
        
        start_ts = max(df_1m.iloc[0]['timestamp'], df_15m.iloc[0]['timestamp'])
        start_idx = df_15m[df_15m['timestamp'] >= start_ts].index[0]
        start_idx = max(start_idx, 200)
        
        print(f"🚀 Iniciando Experimento ATR ({len(df_15m) - start_idx} velas)...")
        
        posicion = None
        
        for i in range(start_idx, len(df_15m) - 1):
            curr_candle = df_15m.iloc[i]
            curr_ts = curr_candle['timestamp']
            
            # GESTIÓN
            if posicion:
                self._gestionar_posicion(posicion, curr_ts, df_1m)
                if posicion['estado'] == 'CERRADA':
                    self.trades_log.append(posicion)
                    posicion = None
            
            # BÚSQUEDA (Motor ALFA1/2)
            if not posicion:
                zona_activa = self._buscar_zona_en_mapa(curr_candle['close'], curr_ts)
                
                if zona_activa:
                    slice_15m = df_15m.iloc[i-20 : i+1]
                    if self._validar_entrada(slice_15m, zona_activa):
                        # Usamos estrategia Híbrida (ALFA2)
                        plan = {
                            'side': 'LONG' if zona_activa['type'] == 'BULLISH' else 'SHORT',
                            'entry': curr_candle['close'],
                            'strategy': f"ALFA2_{zona_activa['type']}"
                        }
                        posicion = self._iniciar_trade(plan, curr_candle, df_1m)

            if i % 1000 == 0: sys.stdout.write(f"\r   ⏳ Escaneando... {i}")

        self._generar_reporte()

    # --- MÉTODOS AUXILIARES ---
    def _buscar_zona_en_mapa(self, precio, timestamp):
        for zona in self.mapa_4h:
            if zona['created_at'] >= timestamp: continue
            if zona['type'] == 'BULLISH':
                if zona['bottom'] <= precio <= zona['top']: return zona
            else:
                if zona['bottom'] <= precio <= zona['top']: return zona
        return None

    def _validar_entrada(self, df_slice, zona):
        vela_actual = df_slice.iloc[-1]
        if not self.smc.validar_fvg_con_obv(df_slice, zona['type']): return False
        analisis = self.lab.analizar_gatillo_vela(vela_actual, vela_actual['rsi'])
        if analisis is None: return False
        if zona['type'] == 'BULLISH' and analisis['tipo'] == 'POSIBLE_LONG': return True
        if zona['type'] == 'BEARISH' and analisis['tipo'] == 'POSIBLE_SHORT': return True
        return False

    def _iniciar_trade(self, plan, candle, df_1m):
        entry_ts = candle['timestamp']
        entry_price = plan['entry']
        side = plan['side']
        
        # Configuración ALFA2
        sl_pct = 0.015
        tp1_pct = 0.05
        
        if side == 'LONG':
            sl_price = entry_price * (1 - sl_pct)
            tp1_price = entry_price * (1 + tp1_pct)
        else:
            sl_price = entry_price * (1 + sl_pct)
            tp1_price = entry_price * (1 - tp1_pct)
            
        dist_sl = abs(entry_price - sl_price)
        qty = 50.0 / dist_sl if dist_sl > 0 else 0

        return {
            'id': len(self.trades_log) + 1,
            'fecha': datetime.fromtimestamp(entry_ts/1000).strftime('%Y-%m-%d %H:%M'),
            'ts_entry': entry_ts,
            'last_check_ts': entry_ts,
            'strategy': plan['strategy'],
            'side': side,
            'entry': entry_price,
            'sl_current': sl_price,
            'tp1': tp1_price,
            'qty': qty,
            'estado': 'ABIERTA',
            'resultado': 'PENDIENTE',
            'pnl': 0.0,
            'tp_level': 0,
            'be_active': False,
            
            # --- VARIABLES DEL EXPERIMENTO ATR ---
            'phantom_atr_triggered': False,
            'phantom_atr_price': 0.0,
            'phantom_pnl': 0.0, # Cuánto hubiéramos ganado/perdido si usábamos ATR
            'highest_price': entry_price, # Récord High (para Long)
            'lowest_price': entry_price   # Récord Low (para Short)
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
            atr_actual = row.get('atr', 0)
            
            # --- 1. MÓDULO EXPERIMENTAL (PHANTOM TRACKER) ---
            if not trade['phantom_atr_triggered'] and atr_actual > 0:
                # Calcular Stop Dinámico (1.5 ATR)
                if side == 'LONG':
                    # Actualizar Máximo
                    if high > trade['highest_price']: trade['highest_price'] = high
                    # Calcular SL Fantasma
                    phantom_sl = trade['highest_price'] - (1.5 * atr_actual)
                    # Verificar Ruptura
                    if low <= phantom_sl:
                        trade['phantom_atr_triggered'] = True
                        trade['phantom_atr_price'] = phantom_sl
                        # Calcular PnL Teórico (sin parcos, salida total)
                        trade['phantom_pnl'] = (phantom_sl - entry) * trade['qty']
                else: # SHORT
                    if low < trade['lowest_price']: trade['lowest_price'] = low
                    phantom_sl = trade['lowest_price'] + (1.5 * atr_actual)
                    if high >= phantom_sl:
                        trade['phantom_atr_triggered'] = True
                        trade['phantom_atr_price'] = phantom_sl
                        trade['phantom_pnl'] = (entry - phantom_sl) * trade['qty']
            
            # --- 2. GESTIÓN REAL (ALFA2) ---
            # Stop Loss
            sl_hit = (side == 'LONG' and low <= trade['sl_current']) or \
                     (side == 'SHORT' and high >= trade['sl_current'])
            if sl_hit:
                self._cerrar(trade, trade['sl_current'], 'STOP_LOSS' if not trade['be_active'] else 'PROTECCION')
                return

            # Break Even (2%)
            roi = (high - entry)/entry if side == 'LONG' else (entry - low)/entry
            if not trade['be_active'] and roi >= 0.02:
                trade['be_active'] = True
                trade['sl_current'] = entry * 1.005 if side == 'LONG' else entry * 0.995

            # TP1 (5%)
            if trade['tp_level'] < 1:
                hit = (side == 'LONG' and high >= trade['tp1']) or (side == 'SHORT' and low <= trade['tp1'])
                if hit:
                    trade['tp_level'] = 1
                    trade['be_active'] = True
                    qty_sold = trade['qty'] * 0.50
                    gain = (trade['tp1'] - entry) * qty_sold if side == 'LONG' else (entry - trade['tp1']) * qty_sold
                    trade['pnl'] += gain
                    self.capital += gain
                    trade['qty'] -= qty_sold

            # TP3 Dinámico (Trailing Smart ALFA2)
            if trade['tp_level'] >= 1:
                adx = row.get('adx', 0)
                rsi = row.get('rsi', 50)
                extremo = rsi > 80 if side == 'LONG' else rsi < 20
                dist = 0.01 if extremo else 0.03
                
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
        trade['pnl'] += diff * trade['qty']
        self.capital += diff * trade['qty']
        
        # Si el Phantom nunca saltó, cerramos la simulación teórica aquí también
        if not trade['phantom_atr_triggered']:
            trade['phantom_atr_price'] = price
            trade['phantom_pnl'] = diff * trade['qty'] # Asumimos qty original para comparativa justa? 
            # Nota: Para comparar estrategias, deberíamos asumir salida total en phantom vs gestión mixta en real.
            # Aquí phantom_pnl ya se calculó con qty total si saltó antes. Si salta al final, usamos qty remanente?
            # Para simplificar el análisis "Phantom", asumimos que si llega al final con la estrategia real, 
            # el Phantom "acepta" ese resultado final.

    def _generar_reporte(self):
        path = os.path.join(self.report_dir, 'reporte_atr_test.csv')
        if not self.trades_log:
            print("\n⚠️ Sin operaciones.")
            return
        
        df = pd.DataFrame(self.trades_log)
        wins = len(df[df['pnl'] > 0])
        print(f"\n📊 RESULTADOS EXPERIMENTO ATR")
        print(f"   Ops: {len(df)} | Wins Real: {wins}")
        print(f"   Capital Final Real: ${self.capital:.2f}")
        
        cols = ['id','fecha','strategy','side','entry','precio_salida','resultado','pnl',
                'phantom_atr_triggered','phantom_atr_price','phantom_pnl']
        df[cols].to_csv(path, index=False)
        print(f"   Reporte: {path}")

if __name__ == "__main__":
    sim = BacktesterSwingATRTest()
    sim.ejecutar_simulacion()