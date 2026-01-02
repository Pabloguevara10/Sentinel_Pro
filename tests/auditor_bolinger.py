# =============================================================================
# NOMBRE: Mega_Auditor_Bollinger.py
# TIPO: Herramienta de Auditoría de Estrategias (Quant Research)
# OBJETIVO: Analizar rompimientos de Bollinger (15m) y rastrear su desenlace
#           hacia la Media o la Banda Opuesta (Mean Reversion vs Trend).
# =============================================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# --- 1. CONFIGURACIÓN DE RUTAS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
# Ajuste para leer la data donde indicaste
data_path_hist = os.path.join(project_root, 'data', 'historical')
data_path_fvg = os.path.join(project_root, 'data', 'historical', 'mapas_fvg')

# =============================================================================
# 2. MOTOR DE INDICADORES (BOLINGER SPECIALIST)
# =============================================================================
class IndicatorEngine:
    @staticmethod
    def add_indicators(df):
        df = df.copy()
        df.columns = [c.lower().strip() for c in df.columns]
        
        # --- A. BANDAS DE BOLLINGER (Standard: 20, 2) ---
        # Puedes ajustar los parámetros aquí si usas otra configuración (ej. 20, 2.5)
        period = 20
        std_dev_mult = 2.0
        
        df['bb_middle'] = df['close'].rolling(window=period).mean()
        df['bb_std'] = df['close'].rolling(window=period).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * std_dev_mult)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * std_dev_mult)
        
        # --- B. INDICADORES DERIVADOS DE BOLLINGER ---
        # 1. Bandwidth: (Upper - Lower) / Middle. Clave para volatilidad.
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100
        
        # 2. %B: Dónde está el precio relativo a las bandas (1=Upper, 0=Lower, 0.5=Middle)
        # Útil para filtrar falsos rompimientos
        df['bb_pct_b'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # --- C. INDICADORES DE CONTEXTO (Filtros) ---
        # RSI para ver divergencias en los extremos
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ATR para normalizar distancias si es necesario
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(14).mean()
        
        return df.dropna()

# =============================================================================
# 3. EL AUDITOR FORENSE (LÓGICA DINÁMICA)
# =============================================================================
class BollingerAuditor:
    def __init__(self):
        self.datasets = {}
        self.report_data = []
        
    def load_data(self):
        print("📂 Cargando Datasets...")
        # Definimos los archivos a buscar según tu estructura
        files = {
            '15m': "AAVEUSDT_15m.csv",
            '1h': "AAVEUSDT_1h.csv",
            '4h': "AAVEUSDT_4h.csv"
        }
        
        for tf, filename in files.items():
            path = os.path.join(data_path_hist, filename)
            # Fallback por si el nombre es diferente (ej. minúsculas)
            if not os.path.exists(path):
                 path = os.path.join(data_path_hist, filename.lower())
                 
            if os.path.exists(path):
                print(f"   ⚙️ Procesando {tf} ({filename})...")
                df = pd.read_csv(path)
                
                # Parsing de fecha estándar
                if 'timestamp' in df.columns:
                    # Detectar si es ms o segundos
                    if df['timestamp'].iloc[0] > 10000000000: # es milisegundos
                         df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    else:
                         df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                
                self.datasets[tf] = IndicatorEngine.add_indicators(df)
            else:
                print(f"   ⚠️ Alerta: No se encontró {path}. La auditoría de contexto {tf} se omitirá.")

    def get_context_snapshot(self, tf, timestamp):
        """Obtiene el estado de las bandas en temporalidades superiores (1H, 4H)."""
        if tf not in self.datasets: return None
        
        df = self.datasets[tf]
        # Buscar índice más cercano anterior (asof)
        idx = df.index.searchsorted(timestamp)
        if idx >= len(df) or idx == 0: return None
        
        # Tomamos el valor anterior para no ver el futuro (closed candle)
        row = df.iloc[idx - 1] 
        
        state = "NEUTRAL"
        if row['close'] > row['bb_upper']: state = "BREAK_UP"
        elif row['close'] < row['bb_lower']: state = "BREAK_DOWN"
        elif row['bb_pct_b'] > 0.8: state = "NEAR_UPPER"
        elif row['bb_pct_b'] < 0.2: state = "NEAR_LOWER"
        
        return {
            f'Context_{tf}_State': state,
            f'Context_{tf}_Width': round(row['bb_width'], 2),
            f'Context_{tf}_RSI': round(row['rsi'], 2)
        }

    def trace_bollinger_path(self, entry_idx, df, side):
        """
        CAMINATA ALEATORIA: Sigue el precio vela a vela hasta tocar objetivos.
        Side: 'UPPER_BREAK' (Precio rompió arriba) o 'LOWER_BREAK' (Precio rompió abajo).
        
        Objetivo Reversión: Tocar Middle Band.
        Objetivo Extremo: Tocar Banda Opuesta.
        """
        entry_price = df.iloc[entry_idx]['close']
        start_row = df.iloc[entry_idx]
        
        # Inicializamos variables de rastreo
        touched_middle = False
        touched_opposite = False
        
        stats = {
            'Bars_To_Middle': 999,
            'MAE_To_Middle_Pct': 0.0, # Max dolor antes de tocar media
            'MFE_To_Middle_Pct': 0.0, # Ganancia al tocar media (si aplica)
            
            'Bars_To_Opposite': 999,
            'MAE_To_Opposite_Pct': 0.0,
            
            'Did_Reverse': False, # Si volvió a la media
            'Did_Cross_Full': False # Si cruzó de banda a banda
        }
        
        # Límites de búsqueda (ej. 200 velas máx hacia el futuro para no iterar eterno)
        max_look_forward = 200
        
        max_adverse_move = 0.0
        max_favorable_move = 0.0
        
        for i in range(1, max_look_forward):
            if entry_idx + i >= len(df): break
            
            curr = df.iloc[entry_idx + i]
            
            # 1. Calcular Excursiones (Asumiendo que apostamos a REVERSIÓN a la media)
            # Si rompió ARRIBA, entramos SHORT -> Ganamos si baja, Perdemos si sube
            if side == 'UPPER_BREAK':
                # Drawdown: Cuánto subió por encima de mi entrada
                move_against = (curr['high'] - entry_price) / entry_price * 100
                # RunUp: Cuánto bajó a mi favor
                move_favor = (entry_price - curr['low']) / entry_price * 100
                
                # Check toque Media (Low toca o cruza la media)
                if not touched_middle and curr['low'] <= curr['bb_middle']:
                    touched_middle = True
                    stats['Bars_To_Middle'] = i
                    stats['MAE_To_Middle_Pct'] = max(max_adverse_move, move_against) # Peor drawdown sufrido
                    stats['Did_Reverse'] = True
                
                # Check toque Opuesta (Low toca o cruza la lower)
                if not touched_opposite and curr['low'] <= curr['bb_lower']:
                    touched_opposite = True
                    stats['Bars_To_Opposite'] = i
                    stats['MAE_To_Opposite_Pct'] = max(max_adverse_move, move_against)
                    stats['Did_Cross_Full'] = True

            # Si rompió ABAJO, entramos LONG -> Ganamos si sube, Perdemos si baja
            else:
                move_against = (entry_price - curr['low']) / entry_price * 100
                move_favor = (curr['high'] - entry_price) / entry_price * 100
                
                if not touched_middle and curr['high'] >= curr['bb_middle']:
                    touched_middle = True
                    stats['Bars_To_Middle'] = i
                    stats['MAE_To_Middle_Pct'] = max(max_adverse_move, move_against)
                    stats['Did_Reverse'] = True
                    
                if not touched_opposite and curr['high'] >= curr['bb_upper']:
                    touched_opposite = True
                    stats['Bars_To_Opposite'] = i
                    stats['MAE_To_Opposite_Pct'] = max(max_adverse_move, move_against)
                    stats['Did_Cross_Full'] = True

            # Actualizar máximos globales de la caminata
            if move_against > max_adverse_move: max_adverse_move = move_against
            if move_favor > max_favorable_move: max_favorable_move = move_favor
            
            # Si ya tocamos ambos objetivos, terminamos antes
            if touched_middle and touched_opposite: break
            
        return stats

    def run_audit(self):
        if '15m' not in self.datasets:
            print("❌ Error: No se cargó el dataset de 15m. Revisa los nombres de archivo.")
            return

        print("\n🔍 INICIANDO AUDITORÍA DE BOLLINGER (15m)...")
        df = self.datasets['15m']
        
        # Iteramos buscando rompimientos
        # Empezamos en 50 para tener historial previo
        for i in range(50, len(df) - 200):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            trigger = False
            side = "NONE"
            
            # DETECTOR DE EVENTOS (TRIGGER)
            # 1. Rompimiento Alcista (Cierre cruza o está por encima de Upper Band)
            # Condición estricta: La vela ANTERIOR estaba dentro, la ACTUAL cierra fuera.
            if prev_row['close'] <= prev_row['bb_upper'] and row['close'] > row['bb_upper']:
                trigger = True; side = 'UPPER_BREAK'
            
            # 2. Rompimiento Bajista
            elif prev_row['close'] >= prev_row['bb_lower'] and row['close'] < row['bb_lower']:
                trigger = True; side = 'LOWER_BREAK'
            
            if not trigger: continue
            
            # --- RECOPILACIÓN DE DATOS (LA PELÍCULA) ---
            
            # 1. Datos Forenses (El Futuro)
            outcome = self.trace_bollinger_path(i, df, side)
            
            # 2. Datos Contextuales (El Pasado Inmediato - La Película)
            # Historial del Ancho de Banda (¿Se estaba expandiendo?)
            width_t0 = row['bb_width']
            width_t1 = df.iloc[i-1]['bb_width']
            width_t2 = df.iloc[i-2]['bb_width']
            width_t3 = df.iloc[i-3]['bb_width']
            
            # Pendiente del ancho de banda (Expansion Rate)
            expansion_rate = width_t0 / width_t3 if width_t3 > 0 else 1
            
            # Contexto Multi-Timeframe
            ctx_1h = self.get_context_snapshot('1h', row.name)
            ctx_4h = self.get_context_snapshot('4h', row.name)
            
            # Construir fila del reporte
            report_row = {
                'Timestamp': row.name,
                'Event_Type': side,
                'Close_Price': row['close'],
                'BB_Width_T0': round(width_t0, 3),
                'BB_Expansion_Rate': round(expansion_rate, 2), # >1 indica explosión
                'RSI_T0': round(row['rsi'], 2),
                
                # La Película del Ancho de Banda (Valores absolutos previos)
                'Width_T-1': round(width_t1, 3),
                'Width_T-2': round(width_t2, 3),
                'Width_T-3': round(width_t3, 3),
                
                # Resultados Forenses (Métricas de Estrategia)
                'Did_Revert_To_Mean': outcome['Did_Reverse'],
                'Bars_To_Mean': outcome['Bars_To_Middle'],
                'MAE_To_Mean_%': round(outcome['MAE_To_Middle_Pct'], 3), # Drawdown aguantado
                
                'Did_Touch_Opposite': outcome['Did_Cross_Full'],
                'Bars_To_Opposite': outcome['Bars_To_Opposite']
            }
            
            # Agregar contexto MTF si existe
            if ctx_1h: report_row.update(ctx_1h)
            if ctx_4h: report_row.update(ctx_4h)
            
            self.report_data.append(report_row)
            
        self.save_report()

    def save_report(self):
        if not self.report_data:
            print("⚠️ No se encontraron eventos.")
            return
            
        df_rep = pd.DataFrame(self.report_data)
        
        # Carpeta reports
        rep_dir = os.path.join(project_root, 'reports')
        if not os.path.exists(rep_dir): os.makedirs(rep_dir)
        
        filename = os.path.join(rep_dir, f"BOLLINGER_AUDIT_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        df_rep.to_csv(filename, index=False)
        
        print("\n" + "="*60)
        print(f"✅ AUDITORÍA FINALIZADA")
        print(f"📊 Eventos Detectados: {len(df_rep)}")
        print(f"📁 Reporte Guardado: {filename}")
        print("="*60)
        print("💡 TIPS DE ANÁLISIS PARA EXCEL:")
        print("   1. Filtra 'Did_Revert_To_Mean' = TRUE.")
        print("   2. Analiza la columna 'MAE_To_Mean_%'. Si es muy alto, la reversión es peligrosa.")
        print("   3. Cruza 'BB_Expansion_Rate' vs 'MAE'.")
        print("      (Hipótesis: Si la expansión es muy fuerte, el precio NO vuelve a la media rápido).")

if __name__ == "__main__":
    auditor = BollingerAuditor()
    auditor.load_data()
    auditor.run_audit()