# =============================================================================
# NOMBRE: Mega_Auditor_Gamma.py
# TIPO: Herramienta de Minería de Datos (Data Mining)
# OBJETIVO: Generar un dataset masivo cruzando 4H, 1H, 15m, 5m con indicadores
#           completos y análisis forense de resultado futuro (MAE/MFE).
# =============================================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN DE RUTAS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
tools_path = os.path.join(project_root, 'tools')
sys.path.append(tools_path)

try:
    from StructureScanner import StructureScanner
    print("✅ Herramientas cargadas correctamente.")
except ImportError as e:
    print(f"❌ Error Crítico: No se pudo importar StructureScanner. {e}")
    sys.exit(1)

# =============================================================================
# 2. MOTOR DE INDICADORES (FÁBRICA MATEMÁTICA)
# =============================================================================
class IndicatorEngine:
    @staticmethod
    def add_all_indicators(df):
        df = df.copy()
        # Normalizar
        df.columns = [c.lower().strip() for c in df.columns]
        
        # 1. EMAs (Tendencia)
        df['ema_9'] = df['close'].ewm(span=9).mean()
        df['ema_21'] = df['close'].ewm(span=21).mean()
        df['ema_50'] = df['close'].ewm(span=50).mean()
        df['ema_200'] = df['close'].ewm(span=200).mean()
        
        # 2. RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 3. MACD
        k_fast = df['close'].ewm(span=12).mean()
        k_slow = df['close'].ewm(span=26).mean()
        df['macd_line'] = k_fast - k_slow
        df['macd_signal'] = df['macd_line'].ewm(span=9).mean()
        df['macd_hist'] = df['macd_line'] - df['macd_signal']
        
        # 4. Stochastic RSI
        min_rsi = df['rsi'].rolling(14).min()
        max_rsi = df['rsi'].rolling(14).max()
        df['stoch_k'] = (df['rsi'] - min_rsi) / (max_rsi - min_rsi)
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        
        # 5. ATR (Volatilidad)
        high, low, close = df['high'], df['low'], df['close']
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()
        
        # 6. ADX (Fuerza)
        up = high - high.shift(1)
        down = low.shift(1) - low
        plus_dm = np.where((up > down) & (up > 0), up, 0)
        minus_dm = np.where((down > up) & (down > 0), down, 0)
        plus_dm = pd.Series(plus_dm, index=df.index)
        minus_dm = pd.Series(minus_dm, index=df.index)
        plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / df['atr'])
        minus_di = 100 * (minus_dm.ewm(alpha=1/14).mean() / df['atr'])
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['adx'] = dx.ewm(alpha=1/14).mean()
        
        # 7. OBV (Volumen Acumulado)
        obv = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        df['obv'] = obv
        
        return df.dropna()

# =============================================================================
# 3. EL MEGA AUDITOR (ORQUESTADOR)
# =============================================================================
class MegaAuditor:
    def __init__(self):
        self.datasets = {}
        self.scanner_4h = None
        self.scanner_1h = None
        self.report_data = []
        
    def load_data(self):
        print("📂 Cargando Datasets Multi-temporales...")
        files = {
            '4h': "../data/historical/AAVEUSDT_4h.csv",
            '1h': "../data/historical/AAVEUSDT_1h.csv",
            '15m': "../data/historical/AAVEUSDT_15m.csv",
            '5m': "../data/historical/AAVEUSDT_5m.csv"
        }
        
        for tf, path in files.items():
            abs_path = os.path.join(os.path.dirname(__file__), path)
            if os.path.exists(abs_path):
                print(f"   ⚙️ Procesando {tf}...")
                df = pd.read_csv(abs_path)
                
                # Timestamp Parsing
                if 'timestamp' in df.columns:
                    if df['timestamp'].iloc[0] > 10000000000:
                         df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    else:
                         df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                
                # Agregar Indicadores
                df = IndicatorEngine.add_all_indicators(df)
                self.datasets[tf] = df
            else:
                print(f"   ❌ Faltante: {path}")
                
        # Inicializar Scanners Estructurales (Fibo/Elliott)
        if '4h' in self.datasets:
            self.scanner_4h = StructureScanner(self.datasets['4h'])
            self.scanner_4h.precompute()
        if '1h' in self.datasets:
            self.scanner_1h = StructureScanner(self.datasets['1h'])
            self.scanner_1h.precompute()

    def get_trend_4h(self, ts):
        """Define el sesgo macro: Bullish, Bearish o Rango."""
        idx = self.datasets['4h'].index.get_indexer([ts], method='pad')[0]
        if idx == -1: return "UNKNOWN"
        row = self.datasets['4h'].iloc[idx]
        
        if row['ema_9'] > row['ema_21'] > row['ema_50']: return "STRONG_BULL"
        if row['ema_9'] < row['ema_21'] < row['ema_50']: return "STRONG_BEAR"
        return "RANGING"

    def get_fibo_context(self, scanner, ts, tf_name):
        """Obtiene si estamos en zona de soporte/resistencia Fibonacci."""
        if not scanner: return "NO_DATA", 0
        idx = scanner.df.index.get_indexer([ts], method='pad')[0]
        if idx == -1: return "NO_DATA", 0
        
        ctx = scanner.get_fibonacci_context(idx)
        if not ctx: return "NO_STRUCTURE", 0
        
        # Devolver nivel más cercano y distancia
        price = scanner.df.iloc[idx]['close']
        nearest_lvl = "NONE"
        min_dist = 999999
        
        for lvl_name, lvl_price in ctx['fibs'].items():
            dist = abs(price - lvl_price) / price
            if dist < min_dist:
                min_dist = dist
                nearest_lvl = lvl_name
                
        status = f"{ctx['mode']}_NEAR_{nearest_lvl}"
        return status, min_dist

    def trace_future_outcome(self, entry_idx, df_15m, side):
        """
        Laboratorio Forense: Mira 48 velas al futuro (12 horas).
        Calcula MAE (Drawdown), MFE (Ganancia) y resultado teórico.
        """
        future_window = 48
        if entry_idx + future_window >= len(df_15m): return None
        
        entry_price = df_15m.iloc[entry_idx]['close']
        future_slice = df_15m.iloc[entry_idx+1 : entry_idx+future_window+1]
        
        if side == 'LONG':
            min_price = future_slice['low'].min()
            max_price = future_slice['high'].max()
            mae_pct = (min_price - entry_price) / entry_price # Drawdown (negativo)
            mfe_pct = (max_price - entry_price) / entry_price # Run Up (positivo)
        else: # SHORT
            max_price = future_slice['high'].max()
            min_price = future_slice['low'].min()
            mae_pct = (entry_price - max_price) / entry_price # Drawdown (negativo)
            mfe_pct = (entry_price - min_price) / entry_price # Run Up (positivo)
            
        return {'mae': mae_pct, 'mfe': mfe_pct}

    def run_audit(self):
        print("\n🔬 INICIANDO MEGA AUDITORÍA (Buscando Convergencias)...")
        df_15m = self.datasets['15m']
        df_5m = self.datasets['5m']
        
        # Iteramos sobre 15m (Timeframe Táctico)
        # Empezamos con margen para tener historial
        for i in range(100, len(df_15m) - 50):
            row_15m = df_15m.iloc[i]
            ts = row_15m.name
            
            # --- 1. DEFINIR GATILLO DE INVESTIGACIÓN ---
            # Para no guardar millones de filas, solo auditamos PUNTOS DE INTERÉS.
            # Gatillo Amplio: RSI sobrevendido/sobrecomprado o Cruce MACD
            trigger = False
            side = "NONE"
            
            # Condición Long (RSI bajo o MACD cruzando arriba)
            if row_15m['rsi'] < 35: 
                trigger = True; side = "LONG"
            # Condición Short
            elif row_15m['rsi'] > 65: 
                trigger = True; side = "SHORT"
            
            if not trigger: continue
            
            # --- 2. CAPTURAR CONTEXTO MACRO (4H / 1H) ---
            trend_4h = self.get_trend_4h(ts)
            struct_4h, dist_4h = self.get_fibo_context(self.scanner_4h, ts, '4h')
            struct_1h, dist_1h = self.get_fibo_context(self.scanner_1h, ts, '1h')
            
            # --- 3. GENERAR MATRIZ DE COMPORTAMIENTO (15m y 5m) ---
            # Snapshots del pasado reciente
            def get_snapshot(df, idx, prefix):
                r = df.iloc[idx]
                return {
                    f'{prefix}_RSI': r['rsi'],
                    f'{prefix}_ADX': r['adx'],
                    f'{prefix}_MACD_Hist': r['macd_hist'],
                    f'{prefix}_StochK': r['stoch_k'],
                    f'{prefix}_OBV_Slope': r['obv'] - df.iloc[idx-1]['obv'] # Cambio OBV
                }

            # Matriz 15m (T-0, T-3, T-6)
            m15_t0 = get_snapshot(df_15m, i, 'M15_T0')
            m15_t3 = get_snapshot(df_15m, i-3, 'M15_T-3')
            
            # Matriz 5m (T-0, T-5, T-10) -> Sincronizar timestamp
            idx_5m = df_5m.index.get_indexer([ts], method='pad')[0]
            if idx_5m == -1: continue
            m5_t0 = get_snapshot(df_5m, idx_5m, 'M5_T0')
            m5_t5 = get_snapshot(df_5m, idx_5m-5, 'M5_T-5')
            
            # --- 4. LABORATORIO FORENSE (Futuro) ---
            outcome = self.trace_future_outcome(i, df_15m, side)
            if not outcome: continue
            
            # --- 5. COMPILAR FILA DEL REPORTE ---
            # Aquí unimos todo en un diccionario plano
            row_data = {
                'Timestamp': ts,
                'Signal_Side': side,
                'Close_Price': row_15m['close'],
                
                # Capa 1: Contexto
                'Trend_4H': trend_4h,
                'Structure_4H': struct_4h,
                'Dist_Fibo_4H_Pct': round(dist_4h * 100, 3),
                'Structure_1H': struct_1h,
                'Dist_Fibo_1H_Pct': round(dist_1h * 100, 3),
                
                # Capa 2: Matriz 15m
                **m15_t0, **m15_t3,
                
                # Capa 2: Matriz 5m
                **m5_t0, **m5_t5,
                
                # Capa 3: Resultado Forense
                'MAE_Pct (Drawdown)': round(outcome['mae'] * 100, 2),
                'MFE_Pct (Potential)': round(outcome['mfe'] * 100, 2),
                'Risk_Reward_Real': round(outcome['mfe'] / abs(outcome['mae']), 2) if outcome['mae'] != 0 else 99
            }
            
            self.report_data.append(row_data)

        self.save_report()

    def save_report(self):
        if not self.report_data:
            print("⚠️ No se encontraron eventos para reportar.")
            return
            
        df = pd.DataFrame(self.report_data)
        
        # Crear directorio reports si no existe
        rep_dir = os.path.join(project_root, 'reports')
        if not os.path.exists(rep_dir): os.makedirs(rep_dir)
        
        filename = os.path.join(rep_dir, f"MEGA_AUDIT_GAMMA_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        df.to_csv(filename, index=False)
        
        print("\n" + "="*60)
        print(f"✅ MEGA AUDITORÍA COMPLETADA")
        print(f"📊 Total Eventos Analizados: {len(df)}")
        print(f"📁 Archivo Guardado: {filename}")
        print("="*60)
        print("💡 SUGERENCIA: Abre este archivo en Excel y filtra por:")
        print("   1. 'MFE_Pct' > 3% (Para ver qué condiciones dieron grandes ganancias)")
        print("   2. 'MAE_Pct' < 0.5% (Para ver entradas perfectas sin drawdown)")

if __name__ == "__main__":
    auditor = MegaAuditor()
    auditor.load_data()
    auditor.run_audit()