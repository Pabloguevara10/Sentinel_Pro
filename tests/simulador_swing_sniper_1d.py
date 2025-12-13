import pandas as pd
import numpy as np
import os
import sys
import traceback
from datetime import datetime

# Ajuste de rutas (Ecosistema)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.config import Config
from tools.precision_lab import PrecisionLab
from tools.smart_money_logic import SmartMoneyLogic
from logic.brain import Brain
from data.calculator import Calculator

class BacktesterSwingSniper1D:
    """
    SIMULADOR SWING SNIPER 1D (Con Telemetría):
    - Lógica: 1D (Zona) -> 1H (OBV) -> 15m (Gatillo).
    - Gestión: Riesgo $100.
    - Telemetría: Registra MAE (Dolor) y MFE (Gloria) para análisis.
    """
    def __init__(self):
        print("\n🦅 INICIANDO SWING SNIPER 1D (Con Telemetría de Dolor/Gloria)...")
        self.cfg = Config()
        self.lab = PrecisionLab()
        self.smc = SmartMoneyLogic()
        self.brain = Brain(self.cfg)
        
        self.capital = 1000.0
        self.trades_log = []
        self.data_cache = {}
        self.mapa_diario = [] 
        self.report_dir = current_dir

    def cargar_recursos(self):
        print("📂 Cargando Data (1d, 1h, 15m, 1m)...")
        for tf in ['1m', '15m', '1h', '1d']:
            path = os.path.join(self.cfg.DIR_DATA, f"{self.cfg.SYMBOL}_{tf}.csv")
            if not os.path.exists(path): 
                print(f"❌ ERROR: Falta data {tf}")
                return False
            try:
                df = pd.read_csv(path)
                if 'ts' in df.columns: df.rename(columns={'ts': 'timestamp'}, inplace=True)
                self.data_cache[tf] = Calculator.calcular_indicadores(df)
            except Exception as e:
                print(f"❌ Error cargando {tf}: {e}")
                return False

        map_path = os.path.join(self.cfg.DIR_DATA, 'mapas_fvg', f"mapa_fvg_1d.csv")
        if not os.path.exists(map_path):
            print("❌ No existe mapa 1D.")
            return False
        
        try:
            self.mapa_diario = pd.read_csv(map_path).to_dict('records')
            print(f"   ✅ Zonas Diarias Cargadas: {len(self.mapa_diario)}")
        except Exception as e:
            print(f"❌ Error mapa 1D: {e}")
            return False
            
        return True

    def ejecutar_simulacion(self):
        if not self.cargar_recursos(): return

        df_1m = self.data_cache['1m']
        df_15m = self.data_cache['15m']
        df_1h = self.data_cache['1h']
        
        start_ts = max(df_1h.iloc[0]['timestamp'], df_15m.iloc[0]['timestamp'])
        start_idx = df_15m[df_15m['timestamp'] >= start_ts].index[0]
        start_idx = max(start_idx, 200)
        
        print(f"🚀 Iniciando Misión Sniper ({len(df_15m) - start_idx} velas)...")
        
        posicion = None
        
        for i in range(start_idx, len(df_15m) - 1):
            curr_candle = df_15m.iloc[i]
            curr_ts = curr_candle['timestamp']
            
            # GESTIÓN (Usamos 1m para precisión en métricas de dolor)
            if posicion:
                self._gestionar_posicion(posicion, curr_ts, df_1m)
                if posicion['estado'] == 'CERRADA':
                    self.trades_log.append(posicion)
                    posicion = None
            
            # ENTRADA
            if not posicion:
                zona_activa = self._buscar_zona_diaria(curr_candle['close'], curr_ts)
                if zona_activa:
                    slice_1h = df_1h[df_1h['timestamp'] <= curr_ts].iloc[-50:]
                    if not slice_1h.empty and self.smc.validar_fvg_con_obv(slice_1h, zona_activa['type']):
                        slice_15m = df_15m.iloc[i-20 : i+1]
                        if self._validar_gatillo_15m(slice_15m, zona_activa['type']):
                            plan = self._calcular_geometria_sniper(slice_15m, zona_activa)
                            if plan:
                                posicion = self._iniciar_trade(plan, curr_candle, df_1m)

            if i % 2000 == 0: sys.stdout.write(f"\r   ⏳ Escaneando... {i}")

        self._generar_reporte()

    def _buscar_zona_diaria(self, precio, timestamp):
        for zona in self.mapa_diario:
            if zona['created_at'] >= timestamp: continue
            if zona['bottom'] <= precio <= zona['top']: return zona
        return None

    def _validar_gatillo_15m(self, df_slice, tipo_zona):
        vela = df_slice.iloc[-1]
        analisis = self.lab.analizar_gatillo_vela(vela, vela.get('rsi', 50))
        if analisis is None: return False
        if tipo_zona == 'BULLISH' and analisis['tipo'] == 'POSIBLE_LONG': return True
        if tipo_zona == 'BEARISH' and analisis['tipo'] == 'POSIBLE_SHORT': return True
        return False

    def _calcular_geometria_sniper(self, df_slice, zona):
        vela_entry = df_slice.iloc[-1]
        atr = vela_entry.get('atr', 0)
        if atr == 0: return None
        
        swing_high = df_slice['high'].max()
        swing_low = df_slice['low'].min()
        entry = vela_entry['close']
        side = 'LONG' if zona['type'] == 'BULLISH' else 'SHORT'
        
        fibs = self.smc.proyectar_target_fibonacci(swing_high, swing_low, side)
        if not fibs: return None
        
        if side == 'LONG':
            sl = swing_low - (atr * 1.5)
            if (entry - sl)/entry < 0.005: sl = entry * 0.995
        else:
            sl = swing_high + (atr * 1.5)
            if (sl - entry)/entry < 0.005: sl = entry * 1.005

        dist_sl = abs(entry - sl)
        qty = 100.0 / dist_sl if dist_sl > 0 else 0 # Riesgo $100
        
        return {
            'side': side, 'entry': entry, 'sl': sl, 'tps': fibs, 'qty': qty,
            'strategy': f"SNIPER_1D_{zona['type']}"
        }

    def _iniciar_trade(self, plan, candle, df_1m):
        entry_ts = candle['timestamp']
        
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
            'radiografia': radiografia,
            # --- TELEMETRÍA ---
            'highest_price': plan['entry'],
            'lowest_price': plan['entry'],
            'max_drawdown_pct': 0.0,
            'max_pnl_potential': 0.0
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
            
            # --- ACTUALIZAR TELEMETRÍA ---
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

            # --- GESTIÓN DE SALIDA ---
            
            # 1. Stop Loss
            sl_hit = (side == 'LONG' and low <= trade['sl_current']) or \
                     (side == 'SHORT' and high >= trade['sl_current'])
            if sl_hit:
                self._cerrar(trade, trade['sl_current'], 'STOP_LOSS' if not trade['be_active'] else 'PROTECCION')
                return

            # 2. Break Even
            roi = (high - entry)/entry if side == 'LONG' else (entry - low)/entry
            if not trade['be_active'] and roi >= 0.02:
                trade['be_active'] = True
                trade['sl_current'] = entry * 1.005 if side == 'LONG' else entry * 0.995

            # 3. TP1 (50%)
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
                    trade['sl_current'] = entry

            # 4. TP2 (Candado)
            if trade['tp_level'] < 2 and trade['tp_level'] >= 1:
                hit = (side == 'LONG' and high >= trade['tp2']) or (side == 'SHORT' and low <= trade['tp2'])
                if hit:
                    trade['tp_level'] = 2
                    trade['sl_current'] = trade['tp1']

            # 5. TP3 (Trailing)
            if trade['tp_level'] >= 2:
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
        
        # Calcular Dinero en Mesa (MFE - PnL Realizado)
        trade['money_on_table'] = max(0, trade['max_pnl_potential'] - trade['pnl'])

    def _generar_reporte(self):
        path = os.path.join(self.report_dir, 'reporte_swing_sniper_1d.csv')
        if not self.trades_log: return
        
        df = pd.DataFrame(self.trades_log)
        wins = len(df[df['pnl'] > 0])
        print(f"\n📊 RESULTADOS SWING SNIPER (1D)")
        print(f"   Ops: {len(df)} | Wins: {wins}")
        print(f"   Win Rate: {(wins/len(df))*100:.1f}%")
        print(f"   Capital Final: ${self.capital:.2f}")
        
        cols = ['id','fecha','strategy','side','entry','precio_salida','resultado','pnl',
                'max_drawdown_pct','max_pnl_potential','money_on_table','radiografia']
        
        final = [c for c in cols if c in df.columns]
        df[final].to_csv(path, index=False)
        print(f"   Reporte: {path}")

if __name__ == "__main__":
    sim = BacktesterSwingSniper1D()
    sim.ejecutar_simulacion()
    