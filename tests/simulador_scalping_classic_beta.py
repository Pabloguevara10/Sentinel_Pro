import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

# Ajuste de rutas (Mismo ecosistema)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.config import Config
from tools.precision_lab import PrecisionLab
from logic.brain import Brain
from data.calculator import Calculator

class BacktesterScalpingClassicBeta:
    """
    SIMULADOR SCALPING CLASSIC BETA (Refinado):
    - Entrada: Fuerza Bruta filtrada por RSI (15m).
    - Gestión: Trailing Stop suavizado en velas de 5m.
    - Métricas: MAE (Dolor), MFE (Dinero en mesa) y Análisis Zombie.
    """
    def __init__(self):
        print("\n🧪 INICIANDO SCALPING BETA (Filtro RSI + Gestión 5m)...")
        self.cfg = Config()
        self.lab = PrecisionLab()
        self.brain = Brain(self.cfg)
        
        self.capital = 1000.0
        self.trades_log = []
        self.data_cache = {}
        self.report_dir = current_dir

    def cargar_datos(self):
        print("📂 Cargando Data (4h, 15m, 5m, 1m)...")
        # AÑADIDO: '5m' para la gestión suavizada
        for tf in ['1m', '5m', '15m', '4h']:
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

        df_1m = self.data_cache['1m'] # Para cálculos finos si se requiere
        df_5m = self.data_cache['5m'] # Para Gestión Suavizada
        df_15m = self.data_cache['15m'] # Para Entrada y Filtro RSI
        df_4h = self.data_cache['4h'] 
        
        start_ts = max(df_5m.iloc[0]['timestamp'], df_15m.iloc[0]['timestamp'])
        start_idx = df_15m[df_15m['timestamp'] >= start_ts].index[0]
        start_idx = max(start_idx, 200)
        
        print(f"🚀 Iniciando Operativa Beta ({len(df_15m) - start_idx} velas)...")
        
        posicion = None
        
        for i in range(start_idx, len(df_15m) - 1):
            curr_candle = df_15m.iloc[i]
            curr_ts = curr_candle['timestamp']
            
            # 1. GESTIÓN (Motor Beta - 5m Suavizado)
            if posicion:
                # Pasamos df_5m en lugar de df_1m para suavizar el trailing
                self._gestionar_posicion(posicion, curr_ts, df_5m)
                if posicion['estado'] == 'CERRADA':
                    self.trades_log.append(posicion)
                    posicion = None
            
            # 2. ENTRADA (Fuerza Bruta + Filtro RSI 15m)
            if not posicion:
                slice_macro = df_4h[df_4h['timestamp'] <= curr_ts].iloc[-100:]
                slice_micro = df_15m.iloc[i-100 : i+1]
                
                # Contexto Brain
                brain_cache = {'1h': slice_macro, '5m': slice_micro}
                signal = self.brain.analizar_mercado(brain_cache)
                
                if signal:
                    # --- NUEVO FILTRO BETA: RSI 15m ---
                    rsi_15m = curr_candle.get('rsi', 50)
                    valid_entry = True
                    
                    if signal['side'] == 'LONG' and rsi_15m > 65:
                        valid_entry = False # Evitar comprar caro
                    if signal['side'] == 'SHORT' and rsi_15m < 35:
                        valid_entry = False # Evitar perseguir precio (vender barato)
                    
                    if valid_entry:
                        plan = {
                            'side': signal['side'],
                            'entry': curr_candle['close'],
                            'strategy': 'SCALPING_BETA'
                        }
                        # Iniciamos trade pasando contexto 1m para radiografía precisa
                        posicion = self._iniciar_trade(plan, curr_candle, df_1m)

            if i % 1000 == 0: sys.stdout.write(f"\r   ⏳ Operando... {i}")

        self._generar_reporte()

    def _iniciar_trade(self, plan, candle, df_1m):
        entry_ts = candle['timestamp']
        entry_price = plan['entry']
        side = plan['side']
        
        # SL/TP Estándar
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

        # Radiografía (RSI 1m para ver el ruido de entrada)
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
            'sl_initial': sl_price, # Para cálculo Zombie
            'sl_current': sl_price,
            'tp1': tp1_price,
            'qty': qty,
            'estado': 'ABIERTA',
            'resultado': 'PENDIENTE',
            'pnl': 0.0,
            'tp_level': 0,
            'be_active': False,
            'radiografia': radiografia,
            # --- NUEVAS METRICAS BETA ---
            'highest_price': entry_price, # Para MFE (Money on Table)
            'lowest_price': entry_price,  # Para MAE (Dolor)
            'max_drawdown_pct': 0.0,
            'max_pnl_potential': 0.0,
            'zombie_recovery': False # Si tocó SL pero luego fue a TP
        }

    def _gestionar_posicion(self, trade, limit_ts, df_data):
        # NOTA: df_data ahora es 5m para suavizar gestión
        candles = df_data[(df_data['timestamp'] > trade['last_check_ts']) & (df_data['timestamp'] <= limit_ts)]
        if candles.empty:
            trade['last_check_ts'] = limit_ts
            return

        side = trade['side']
        entry = trade['entry']
        
        for _, row in candles.iterrows():
            high, low, close = row['high'], row['low'], row['close']
            
            # --- ACTUALIZAR MÉTRICAS BETA (Dolor y Potencial) ---
            if high > trade['highest_price']: trade['highest_price'] = high
            if low < trade['lowest_price']: trade['lowest_price'] = low
            
            # Calcular Drawdown actual (Dolor)
            current_dd = 0.0
            current_profit_potential = 0.0
            
            if side == 'LONG':
                # Dolor: Cuánto bajó desde la entrada
                if low < entry:
                    dd_dist = entry - low
                    current_dd = (dd_dist / entry) * 100
                # Potencial: Cuánto subió máximo
                if high > entry:
                    profit_dist = high - entry
                    current_profit_potential = profit_dist * trade['qty']
            else: # SHORT
                # Dolor: Cuánto subió desde la entrada
                if high > entry:
                    dd_dist = high - entry
                    current_dd = (dd_dist / entry) * 100
                # Potencial: Cuánto bajó máximo
                if low < entry:
                    profit_dist = entry - low
                    current_profit_potential = profit_dist * trade['qty']

            # Guardar peores/mejores registros
            if current_dd > trade['max_drawdown_pct']: trade['max_drawdown_pct'] = current_dd
            if current_profit_potential > trade['max_pnl_potential']: trade['max_pnl_potential'] = current_profit_potential

            # --- LÓGICA DE SALIDA ---
            
            # 1. Stop Loss
            sl_hit = (side == 'LONG' and low <= trade['sl_current']) or \
                     (side == 'SHORT' and high >= trade['sl_current'])
            if sl_hit:
                # Antes de cerrar, revisar si fue un "Zombie" (mirar futuro 4h)
                self._analisis_zombie(trade, row['timestamp'], df_data)
                self._cerrar(trade, trade['sl_current'], 'STOP_LOSS' if not trade['be_active'] else 'PROTECCION')
                return

            # 2. Break Even (2%)
            roi = (high - entry)/entry if side == 'LONG' else (entry - low)/entry
            if not trade['be_active'] and roi >= 0.02:
                trade['be_active'] = True
                trade['sl_current'] = entry * 1.005 if side == 'LONG' else entry * 0.995

            # 3. TP1 (5%) -> Cobrar 50%
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

            # 4. Trailing Smart (Suavizado con datos de 5m)
            if trade['tp_level'] >= 1:
                rsi = row.get('rsi', 50)
                # Mismo criterio pero aplicado a velas de 5m -> Menos ruido
                extremo = rsi > 80 if side == 'LONG' else rsi < 20
                dist = 0.01 if extremo else 0.02 
                
                if side == 'LONG':
                    new_sl = close * (1 - dist)
                    if new_sl > trade['sl_current']: trade['sl_current'] = new_sl
                else:
                    new_sl = close * (1 + dist)
                    if new_sl < trade['sl_current']: trade['sl_current'] = new_sl

        trade['last_check_ts'] = limit_ts

    def _analisis_zombie(self, trade, sl_timestamp, df_data):
        """
        Mira hacia el futuro (48 velas de 5m = 4 horas) para ver si el precio
        hubiera tocado el TP1 si no nos hubiera sacado el SL.
        """
        if trade['be_active']: return # Si ya estaba en BE, no cuenta como zombie doloroso
        
        future_window = df_data[df_data['timestamp'] > sl_timestamp].head(48)
        if future_window.empty: return

        tp_price = trade['tp1']
        side = trade['side']
        
        recovered = False
        for _, row in future_window.iterrows():
            if side == 'LONG':
                if row['high'] >= tp_price:
                    recovered = True
                    break
            else:
                if row['low'] <= tp_price:
                    recovered = True
                    break
        
        trade['zombie_recovery'] = recovered

    def _cerrar(self, trade, price, reason):
        trade['estado'] = 'CERRADA'
        trade['resultado'] = reason
        trade['precio_salida'] = price
        
        diff = (price - trade['entry']) if trade['side'] == 'LONG' else (trade['entry'] - price)
        gain = diff * trade['qty']
        
        trade['pnl'] += gain
        self.capital += gain
        
        # Calcular Dinero dejado en la mesa (MFE - Realized)
        # Si el PnL realizado es menor que el potencial máximo que vimos
        trade['money_on_table'] = max(0, trade['max_pnl_potential'] - trade['pnl'])

    def _generar_reporte(self):
        path = os.path.join(self.report_dir, 'reporte_scalping_classic_beta.csv')
        if not self.trades_log: return
        
        df = pd.DataFrame(self.trades_log)
        wins = len(df[df['pnl'] > 0])
        print(f"\n📊 RESULTADOS SCALPING BETA")
        print(f"   Ops: {len(df)} | Wins: {wins}")
        print(f"   Win Rate: {(wins/len(df))*100:.1f}%")
        print(f"   Capital Final: ${self.capital:.2f}")
        
        cols = ['id','fecha','strategy','side','entry','precio_salida','resultado','pnl',
                'max_drawdown_pct', 'money_on_table', 'zombie_recovery', 'radiografia']
        
        final = [c for c in cols if c in df.columns]
        df[final].to_csv(path, index=False)
        print(f"   Reporte Generado: {path}")

if __name__ == "__main__":
    sim = BacktesterScalpingClassicBeta()
    sim.ejecutar_simulacion()