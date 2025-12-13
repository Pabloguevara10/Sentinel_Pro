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

class BacktesterSwingAlfa1:
    """
    SIMULADOR SWING ALFA1 (DOBLE LOTAJE):
    Versión con reportes de error explícitos y riesgo x2.
    """
    def __init__(self):
        print("\n🦅 LABORATORIO SWING ALFA1 (DOBLE LOTAJE)...")
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
            if not os.path.exists(path): 
                print(f"❌ ERROR FATAL: No existe el archivo {path}")
                return False
            try:
                df = pd.read_csv(path)
                if 'ts' in df.columns: df.rename(columns={'ts': 'timestamp'}, inplace=True)
                self.data_cache[tf] = Calculator.calcular_indicadores(df)
                
            except Exception as e:
                print(f"\n❌ ERROR CRÍTICO cargando {tf}:")
                print(f"   Mensaje: {str(e)}")
                traceback.print_exc()
                return False

        map_path = os.path.join(self.cfg.DIR_DATA, 'mapas_fvg', f"mapa_fvg_4h.csv")
        print(f"🗺️ Cargando Mapa: {map_path}")
        if not os.path.exists(map_path):
            print("❌ ERROR: No existe el mapa. Ejecuta 'tools/fvg_scanner.py'.")
            return False
        
        try:
            self.mapa_4h = pd.read_csv(map_path).to_dict('records')
            print(f"   ✅ Zonas Cargadas: {len(self.mapa_4h)}")
        except Exception as e:
            print(f"❌ Error leyendo mapa: {e}")
            return False
            
        return True

    def ejecutar_simulacion(self):
        if not self.cargar_recursos(): 
            print("⚠️ Simulación abortada.")
            return

        df_1m = self.data_cache['1m']
        df_15m = self.data_cache['15m']
        
        start_ts = max(df_1m.iloc[0]['timestamp'], df_15m.iloc[0]['timestamp'])
        start_idx = df_15m[df_15m['timestamp'] >= start_ts].index[0]
        start_idx = max(start_idx, 200)
        
        print(f"🚀 Iniciando Misión ALFA1 ({len(df_15m) - start_idx} velas)...")
        
        posicion = None
        
        for i in range(start_idx, len(df_15m) - 1):
            curr_candle = df_15m.iloc[i]
            curr_ts = curr_candle['timestamp']
            
            if posicion:
                self._gestionar_posicion(posicion, curr_ts, df_1m)
                if posicion['estado'] == 'CERRADA':
                    self.trades_log.append(posicion)
                    posicion = None
            
            if not posicion:
                zona_activa = self._buscar_zona_en_mapa(curr_candle['close'], curr_ts)
                if zona_activa:
                    slice_15m = df_15m.iloc[i-20 : i+1]
                    if self._validar_entrada(slice_15m, zona_activa):
                        plan = self._calcular_geometria(slice_15m, zona_activa)
                        if plan:
                            posicion = self._iniciar_trade(plan, curr_candle, df_1m)

            if i % 1000 == 0: sys.stdout.write(f"\r   ⏳ Escaneando... {i}")

        self._generar_reporte()

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
        if 'obv' not in df_slice.columns: return False
        if not self.smc.validar_fvg_con_obv(df_slice, zona['type']): return False
        analisis = self.lab.analizar_gatillo_vela(vela_actual, vela_actual['rsi'])
        if analisis is None: return False
        if zona['type'] == 'BULLISH' and analisis['tipo'] == 'POSIBLE_LONG': return True
        if zona['type'] == 'BEARISH' and analisis['tipo'] == 'POSIBLE_SHORT': return True
        return False

    def _calcular_geometria(self, df_slice, zona):
        vela_entry = df_slice.iloc[-1]
        atr = vela_entry.get('atr', 0)
        if atr == 0: return None
        
        swing_high = df_slice['high'].max()
        swing_low = df_slice['low'].min()
        entry_price = vela_entry['close']
        side = 'LONG' if zona['type'] == 'BULLISH' else 'SHORT'
        
        fibs = self.smc.proyectar_target_fibonacci(swing_high, swing_low, side)
        if not fibs: return None
        
        if side == 'LONG':
            sl_price = swing_low - (atr * 1.5)
            if (entry_price - sl_price) / entry_price < 0.005: sl_price = entry_price * 0.995
        else:
            sl_price = swing_high + (atr * 1.5)
            if (sl_price - entry_price) / entry_price < 0.005: sl_price = entry_price * 1.005

        distancia_sl = abs(entry_price - sl_price)
        
        # --- CAMBIO: DOBLE LOTAJE ($100 RIESGO) ---
        riesgo_usd = 100.0 
        # ------------------------------------------
        
        qty = riesgo_usd / distancia_sl if distancia_sl > 0 else 0
        
        return {
            'side': side,
            'entry': entry_price,
            'sl': sl_price,
            'tps': fibs,
            'qty': qty,
            'strategy': f"ALFA1_{zona['type']}"
        }

    def _iniciar_trade(self, plan, candle, df_1m):
        entry_ts = candle['timestamp']
        subset = df_1m[df_1m['timestamp'] <= entry_ts]
        radiografia = "N/A"
        if not subset.empty:
            idx = subset.index[-1]
            radio_data = df_1m.iloc[max(0, idx-5):idx]
            radiografia = " || ".join([f"RSI:{r.get('rsi',0):.0f}" for _, r in radio_data.iterrows()])

        return {
            'id': len(self.trades_log) + 1,
            'fecha': datetime.fromtimestamp(entry_ts/1000).strftime('%Y-%m-%d %H:%M'),
            'ts_entry': entry_ts,
            'last_check_ts': entry_ts,
            'strategy': plan['strategy'],
            'side': plan['side'],
            'entry': plan['entry'],
            'sl_current': plan['sl'],
            'tp1': plan['tps']['tp1'],
            'tp2': plan['tps']['tp2'],
            'qty': plan['qty'],
            'estado': 'ABIERTA',
            'resultado': 'PENDIENTE',
            'pnl': 0.0,
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
            
            # SL
            sl_hit = (side == 'LONG' and low <= trade['sl_current']) or \
                     (side == 'SHORT' and high >= trade['sl_current'])
            if sl_hit:
                self._cerrar(trade, trade['sl_current'], 'STOP_LOSS' if not trade['be_active'] else 'PROTECCION')
                return

            # BE (>2%)
            roi = (high - entry)/entry if side == 'LONG' else (entry - low)/entry
            if not trade['be_active'] and roi >= 0.02:
                trade['be_active'] = True
                trade['sl_current'] = entry * 1.005 if side == 'LONG' else entry * 0.995

            # TP1 (Fibonacci 1.0)
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

            # TP2 (Fibonacci 1.618)
            if trade['tp_level'] < 2 and trade['tp_level'] >= 1:
                hit = (side == 'LONG' and high >= trade['tp2']) or (side == 'SHORT' and low <= trade['tp2'])
                if hit:
                    trade['tp_level'] = 2
                    trade['sl_current'] = trade['tp1']

            # TP3 Dinámico
            if trade['tp_level'] >= 2:
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

    def _generar_reporte(self):
        path = os.path.join(self.report_dir, 'reporte_alfa1_doble.csv')
        if not self.trades_log:
            print("\n⚠️ Sin operaciones ALFA1.")
            return
        
        df = pd.DataFrame(self.trades_log)
        wins = len(df[df['pnl'] > 0])
        print(f"\n📊 RESULTADOS ALFA1 (DOBLE LOTAJE)")
        print(f"   Ops: {len(df)} | Wins: {wins}")
        print(f"   Capital Final: ${self.capital:.2f}")
        df.to_csv(path, index=False)
        print(f"   Reporte: {path}")

if __name__ == "__main__":
    sim = BacktesterSwingAlfa1()
    sim.ejecutar_simulacion()