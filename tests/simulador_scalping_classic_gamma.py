import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

# Ajuste de rutas (Ecosistema)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.config import Config
from tools.precision_lab import PrecisionLab
from logic.brain import Brain
from data.calculator import Calculator

class BacktesterScalpingClassicGamma:
    """
    SIMULADOR SCALPING CLASSIC GAMMA (Volumen + Gestión Macro):
    - Entrada: Fuerza Bruta (Sin filtros restrictivos).
    - Gestión: Trailing Stop relajado (15m).
    - TP2 Dinámico: Toma parciales a $150 USD.
    - Marcadores: Detecta 'Chasing' en Shorts verticales.
    """
    def __init__(self):
        print("\n🌪️ INICIANDO SCALPING GAMMA (Volumen & Trailing 15m)...")
        self.cfg = Config()
        self.lab = PrecisionLab()
        self.brain = Brain(self.cfg)
        
        self.capital = 1000.0
        self.trades_log = []
        self.data_cache = {}
        self.report_dir = current_dir

    def cargar_datos(self):
        print("📂 Cargando Data (4h, 15m, 1m)...")
        # Usamos 15m tanto para Entrada como para Gestión relajada
        for tf in ['1m', '15m', '4h']:
            path = os.path.join(self.cfg.DIR_DATA, f"{self.cfg.SYMBOL}_{tf}.csv")
            if not os.path.exists(path): return False
            try:
                df = pd.read_csv(path)
                if 'ts' in df.columns: df.rename(columns={'ts': 'timestamp'}, inplace=True)
                self.data_cache[tf] = Calculator.calcular_indicadores(df)
            except: return False
        return True

    def ejecutar_simulacion(self):
        if not self.cargar_datos(): return

        df_1m = self.data_cache['1m']   # Radiografía
        df_15m = self.data_cache['15m'] # Entrada y Gestión
        df_4h = self.data_cache['4h']   # Contexto
        
        start_ts = max(df_1m.iloc[0]['timestamp'], df_15m.iloc[0]['timestamp'])
        start_idx = df_15m[df_15m['timestamp'] >= start_ts].index[0]
        start_idx = max(start_idx, 200)
        
        print(f"🚀 Iniciando Operativa Gamma ({len(df_15m) - start_idx} velas)...")
        
        posicion = None
        
        for i in range(start_idx, len(df_15m) - 1):
            curr_candle = df_15m.iloc[i]
            curr_ts = curr_candle['timestamp']
            
            # 1. GESTIÓN (Motor Gamma - 15m Relajado)
            if posicion:
                # Pasamos df_15m para que el trailing sea lento y deje correr
                self._gestionar_posicion(posicion, curr_ts, df_15m)
                if posicion['estado'] == 'CERRADA':
                    self.trades_log.append(posicion)
                    posicion = None
            
            # 2. ENTRADA (Fuerza Bruta - Sin Filtros RSI)
            if not posicion:
                slice_macro = df_4h[df_4h['timestamp'] <= curr_ts].iloc[-100:]
                slice_micro = df_15m.iloc[i-100 : i+1]
                
                brain_cache = {'1h': slice_macro, '5m': slice_micro}
                signal = self.brain.analizar_mercado(brain_cache)
                
                if signal:
                    # Detección de 'Chasing' (Anti-Chasing Marker)
                    # Calculamos pendiente del RSI de las últimas velas
                    rsi_now = curr_candle.get('rsi', 50)
                    rsi_prev = df_15m.iloc[i-1].get('rsi', 50)
                    rsi_slope = rsi_now - rsi_prev
                    
                    # Marcamos si es una venta en caída libre (> 7 puntos de caída en una vela)
                    is_chasing = (signal['side'] == 'SHORT' and rsi_slope < -7)
                    
                    plan = {
                        'side': signal['side'],
                        'entry': curr_candle['close'],
                        'strategy': 'SCALPING_GAMMA',
                        'is_chasing': is_chasing,
                        'rsi_slope': rsi_slope
                    }
                    posicion = self._iniciar_trade(plan, curr_candle, df_1m)

            if i % 1000 == 0: sys.stdout.write(f"\r   ⏳ Operando... {i}")

        self._generar_reporte()

    def _iniciar_trade(self, plan, candle, df_1m):
        entry_ts = candle['timestamp']
        entry_price = plan['entry']
        side = plan['side']
        
        # SL 1.5% / TP1 5%
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

        # Radiografía
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
            # Métricas Gamma
            'is_chasing': plan['is_chasing'],
            'rsi_slope_entry': plan['rsi_slope'],
            'max_pnl_potential': 0.0,
            'max_drawdown_pct': 0.0,
            'radiografia': radiografia,
            'highest_price': entry_price,
            'lowest_price': entry_price
        }

    def _gestionar_posicion(self, trade, limit_ts, df_data):
        # df_data es 15m (Relajado)
        candles = df_data[(df_data['timestamp'] > trade['last_check_ts']) & (df_data['timestamp'] <= limit_ts)]
        if candles.empty:
            trade['last_check_ts'] = limit_ts
            return

        side = trade['side']
        entry = trade['entry']
        
        for _, row in candles.iterrows():
            high, low, close = row['high'], row['low'], row['close']
            
            # Actualizar Métricas (Dolor/Potencial)
            if high > trade['highest_price']: trade['highest_price'] = high
            if low < trade['lowest_price']: trade['lowest_price'] = low
            
            current_pnl_val = 0.0
            current_dd = 0.0
            
            if side == 'LONG':
                current_pnl_val = (high - entry) * trade['qty']
                if low < entry: current_dd = ((entry - low)/entry)*100
            else:
                current_pnl_val = (entry - low) * trade['qty']
                if high > entry: current_dd = ((high - entry)/entry)*100
                
            if current_pnl_val > trade['max_pnl_potential']: trade['max_pnl_potential'] = current_pnl_val
            if current_dd > trade['max_drawdown_pct']: trade['max_drawdown_pct'] = current_dd

            # --- LÓGICA DE SALIDA ---

            # 1. Stop Loss
            sl_hit = (side == 'LONG' and low <= trade['sl_current']) or \
                     (side == 'SHORT' and high >= trade['sl_current'])
            if sl_hit:
                self._cerrar(trade, trade['sl_current'], 'STOP_LOSS' if not trade['be_active'] else 'PROTECCION')
                return

            # 2. Break Even (2%)
            roi = (high - entry)/entry if side == 'LONG' else (entry - low)/entry
            if not trade['be_active'] and roi >= 0.02:
                trade['be_active'] = True
                trade['sl_current'] = entry * 1.005 if side == 'LONG' else entry * 0.995

            # 3. TP1 (5% ROI) -> Cobrar 50%
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

            # 4. TP2 DINÁMICO (Nuevo)
            # Si ganancia flotante supera $150, cerramos 25% extra (Lock Profit)
            if trade['tp_level'] < 2 and current_pnl_val >= 150.0:
                trade['tp_level'] = 2
                trade['be_active'] = True
                
                # Calcular precio de cierre parcial (aprox close actual)
                exit_price = close
                qty_sold = trade['qty'] * 0.25 # Vender 25% del remanente
                
                diff = (exit_price - entry) if side == 'LONG' else (entry - exit_price)
                gain = diff * qty_sold
                
                trade['pnl'] += gain
                self.capital += gain
                trade['qty'] -= qty_sold
                
                # Apretar SL al precio de entrada (Hard BE) o dejar trailing actuar
                # Al ser dinámico, confiamos en el Trailing de abajo

            # 5. Trailing Smart (Relajado 15m)
            if trade['tp_level'] >= 1:
                rsi = row.get('rsi', 50)
                extremo = rsi > 80 if side == 'LONG' else rsi < 20
                dist = 0.015 if extremo else 0.03 # Más holgado que en beta (era 0.01/0.02)
                
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
        
        # Calcular Dinero en Mesa (Solo de la posición remanente)
        trade['money_on_table'] = max(0, trade['max_pnl_potential'] - trade['pnl'])

    def _generar_reporte(self):
        path = os.path.join(self.report_dir, 'reporte_scalping_classic_gamma.csv')
        if not self.trades_log: return
        
        df = pd.DataFrame(self.trades_log)
        wins = len(df[df['pnl'] > 0])
        print(f"\n📊 RESULTADOS SCALPING GAMMA")
        print(f"   Ops: {len(df)} | Wins: {wins}")
        print(f"   Win Rate: {(wins/len(df))*100:.1f}%")
        print(f"   Capital Final: ${self.capital:.2f}")
        
        cols = ['id','fecha','strategy','side','entry','precio_salida','resultado','pnl',
                'is_chasing','rsi_slope_entry','max_pnl_potential','money_on_table']
        
        final = [c for c in cols if c in df.columns]
        df[final].to_csv(path, index=False)
        print(f"   Reporte Generado: {path}")

if __name__ == "__main__":
    sim = BacktesterScalpingClassicGamma()
    sim.ejecutar_simulacion()