import pandas as pd
import numpy as np
import os
import sys
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

class BacktesterSwingAlfa2:
    """
    SIMULADOR ALFA2 (HÍBRIDO):
    - MOTOR DE ENTRADA: ALFA1 (Mapas FVG + OBV + Gatillo) -> Alta Precisión.
    - MOTOR DE SALIDA: V1.2 (TP1 5% + Trailing Smart) -> Alta Rentabilidad.
    """
    def __init__(self):
        print("\n🦅 LABORATORIO ALFA2 (HÍBRIDO: PRECISIÓN + CAJA)...")
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
        # 1. Cargar Precios
        print("📂 Cargando Data (4h, 15m, 1m)...")
        for tf in ['1m', '15m', '4h']:
            path = os.path.join(self.cfg.DIR_DATA, f"{self.cfg.SYMBOL}_{tf}.csv")
            if not os.path.exists(path): return False
            try:
                df = pd.read_csv(path)
                if 'ts' in df.columns: df.rename(columns={'ts': 'timestamp'}, inplace=True)
                self.data_cache[tf] = Calculator.calcular_indicadores(df)
            except: return False

        # 2. Cargar Mapa FVG 4H (Motor ALFA1)
        map_path = os.path.join(self.cfg.DIR_DATA, 'mapas_fvg', f"mapa_fvg_4h.csv")
        print(f"🗺️ Cargando Mapa: {map_path}")
        if not os.path.exists(map_path):
            print("❌ Error: Ejecuta 'tools/fvg_scanner.py'.")
            return False
        
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
        
        print(f"🚀 Iniciando Misión ALFA2 ({len(df_15m) - start_idx} velas)...")
        
        posicion = None
        
        for i in range(start_idx, len(df_15m) - 1):
            curr_candle = df_15m.iloc[i]
            curr_ts = curr_candle['timestamp']
            
            # 1. GESTIÓN (Motor V1.2)
            if posicion:
                self._gestionar_posicion(posicion, curr_ts, df_1m)
                if posicion['estado'] == 'CERRADA':
                    self.trades_log.append(posicion)
                    posicion = None
            
            # 2. BÚSQUEDA (Motor ALFA1)
            if not posicion:
                zona_activa = self._buscar_zona_en_mapa(curr_candle['close'], curr_ts)
                
                if zona_activa:
                    slice_15m = df_15m.iloc[i-20 : i+1]
                    
                    if self._validar_entrada(slice_15m, zona_activa):
                        # Si valida, entramos con gestión V1.2
                        plan = {
                            'side': 'LONG' if zona_activa['type'] == 'BULLISH' else 'SHORT',
                            'entry': curr_candle['close'],
                            'strategy': f"ALFA2_{zona_activa['type']}"
                        }
                        posicion = self._iniciar_trade(plan, curr_candle, df_1m)

            if i % 1000 == 0: sys.stdout.write(f"\r   ⏳ Escaneando... {i}")

        self._generar_reporte()

    # --- MOTOR DE ENTRADA (ALFA1) ---
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
        
        # Validación OBV (SMC)
        if not self.smc.validar_fvg_con_obv(df_slice, zona['type']):
            return False
            
        # Validación Gatillo (Mecha)
        analisis = self.lab.analizar_gatillo_vela(vela_actual, vela_actual['rsi'])
        if analisis is None: return False
        
        if zona['type'] == 'BULLISH' and analisis['tipo'] == 'POSIBLE_LONG': return True
        if zona['type'] == 'BEARISH' and analisis['tipo'] == 'POSIBLE_SHORT': return True
        return False

    # --- MOTOR DE GESTIÓN (V1.2) ---
    def _iniciar_trade(self, plan, candle, df_1m):
        entry_ts = candle['timestamp']
        subset = df_1m[df_1m['timestamp'] <= entry_ts]
        radiografia = "N/A"
        if not subset.empty:
            idx = subset.index[-1]
            radio_data = df_1m.iloc[max(0, idx-5):idx]
            radiografia = " || ".join([f"RSI:{r.get('rsi',0):.0f}" for _, r in radio_data.iterrows()])

        entry_price = plan['entry']
        side = plan['side']
        
        # Reglas V1.2: SL 1.5%, TP1 5%
        sl_pct = 0.015
        tp1_pct = 0.05
        
        if side == 'LONG':
            sl_price = entry_price * (1 - sl_pct)
            tp1_price = entry_price * (1 + tp1_pct)
        else:
            sl_price = entry_price * (1 + sl_pct)
            tp1_price = entry_price * (1 - tp1_pct)
            
        # Qty estimada para riesgo de $50 (5% de 1000)
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
            
            # SL (1.5%)
            sl_hit = (side == 'LONG' and low <= trade['sl_current']) or \
                     (side == 'SHORT' and high >= trade['sl_current'])
            if sl_hit:
                reason = 'STOP_LOSS'
                if trade['be_active']: reason = 'PROTECCION'
                if trade['tp_level'] >= 1: reason = 'TRAILING_STOP'
                self._cerrar(trade, trade['sl_current'], reason)
                return

            # BE (2%) -> Mover SL a Entrada + 0.5%
            roi = (high - entry)/entry if side == 'LONG' else (entry - low)/entry
            if not trade['be_active'] and roi >= 0.02:
                trade['be_active'] = True
                trade['sl_current'] = entry * 1.005 if side == 'LONG' else entry * 0.995

            # TP1 (5%) -> Cobrar 50%
            if trade['tp_level'] < 1:
                hit = (side == 'LONG' and high >= trade['tp1']) or (side == 'SHORT' and low <= trade['tp1'])
                if hit:
                    trade['tp_level'] = 1
                    trade['be_active'] = True
                    
                    qty_sold = trade['qty'] * 0.50
                    gain = (trade['tp1'] - entry) * qty_sold if side == 'LONG' else (entry - trade['tp1']) * qty_sold
                    trade['pnl'] += gain
                    self.capital += gain
                    trade['qty'] -= qty_sold # Reducir

            # Trailing Smart (Surfer Mode)
            if trade['tp_level'] >= 1:
                adx = row.get('adx', 0)
                rsi = row.get('rsi', 50)
                extremo = rsi > 80 if side == 'LONG' else rsi < 20
                dist = 0.01 if extremo else 0.03 # 3% de aire
                
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
        gain = diff * trade['qty']
        trade['pnl'] += gain
        self.capital += gain

    def _generar_reporte(self):
        path = os.path.join(self.report_dir, 'reporte_alfa2.csv')
        if not self.trades_log:
            print("\n⚠️ Sin operaciones ALFA2.")
            return
        
        df = pd.DataFrame(self.trades_log)
        wins = len(df[df['pnl'] > 0])
        print(f"\n📊 RESULTADOS ALFA2 (HÍBRIDO)")
        print(f"   Ops: {len(df)} | Wins: {wins}")
        print(f"   Win Rate: {(wins/len(df))*100:.1f}%")
        print(f"   Capital Final: ${self.capital:.2f}")
        df.to_csv(path, index=False)
        print(f"   Reporte: {path}")

if __name__ == "__main__":
    sim = BacktesterSwingAlfa2()
    sim.ejecutar_simulacion()