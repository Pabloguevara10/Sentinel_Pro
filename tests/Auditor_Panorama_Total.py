# =============================================================================
# UBICACIÓN: tests/Auditor_Panorama_Total.py
# DESCRIPCIÓN: Auditoría de "Película Completa" (Time-Lapse Analysis)
# ALCANCE: 10 velas antes -> ENTRADA -> 10 velas después
# OBJETIVO: Entender el comportamiento dinámico de los indicadores.
# =============================================================================

import pandas as pd
import numpy as np
import os
import warnings
from scipy.signal import argrelextrema

warnings.filterwarnings('ignore')

# --- CONFIGURACIÓN ---
SYMBOL = "AAVEUSDT"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, "data", "historical", f"{SYMBOL}_1m.csv")

# Ventana de Análisis (La "Película")
LOOKBACK = 10  # Velas antes
LOOKFORWARD = 10 # Velas después (Para análisis forense, no para el bot en vivo)

# Criterios de Clasificación (Para saber quién es quién)
TARGET_PROFIT = 0.02 # +2%
MAX_LOSS = -0.02     # -2%
TIME_LIMIT_MIN = 240 # 4 Horas

# =============================================================================
# 1. MOTOR DE PROCESAMIENTO
# =============================================================================
def preparar_data(df):
    # Indicadores Clave
    df['rsi'] = 100 - (100 / (1 + (df['close'].diff().where(lambda x: x>0,0).rolling(14).mean() / 
                                   -df['close'].diff().where(lambda x: x<0,0).rolling(14).mean().replace(0,0.001))))
    
    k = df['close'].ewm(span=12).mean(); d = df['close'].ewm(span=26).mean()
    df['macd_hist'] = (k-d) - (k-d).ewm(span=9).mean()
    
    df['ema_200'] = df['close'].ewm(span=200).mean()
    
    # ATR Normalizado (% del precio) para comparar peras con peras
    tr = pd.concat([df['high']-df['low'], (df['high']-df['close'].shift(1)).abs(), (df['low']-df['close'].shift(1)).abs()], axis=1).max(axis=1)
    df['atr_pct'] = (tr.rolling(14).mean() / df['close']) * 100
    
    return df.dropna()

class StructureScanner:
    def __init__(self, df):
        self.df = df.copy()
        # Precompute simple de máximos locales
        self.df['pivot_h'] = self.df['high'][(self.df['high'].shift(1) < self.df['high']) & (self.df['high'].shift(-1) < self.df['high'])]
        self.df['pivot_l'] = self.df['low'][(self.df['low'].shift(1) > self.df['low']) & (self.df['low'].shift(-1) > self.df['low'])]

    def get_fibo_dist(self, ts, price):
        try:
            # Buscar últimos 2 pivotes válidos antes de TS
            past = self.df.loc[:ts].iloc[:-1]
            last_h = past['pivot_h'].last_valid_index()
            last_l = past['pivot_l'].last_valid_index()
            
            if not last_h or not last_l: return 999
            
            h_val = past.loc[last_h]['high']
            l_val = past.loc[last_l]['low']
            
            diff = abs(h_val - l_val)
            if diff == 0: return 999
            
            # Niveles Fibo Standard
            levels = [h_val - (diff*r) for r in [0.382, 0.5, 0.618]] if h_val > l_val else [l_val + (diff*r) for r in [0.382, 0.5, 0.618]]
            return min([abs(price - l)/price for l in levels])
        except: return 999

# =============================================================================
# 2. AUDITOR PANORÁMICO
# =============================================================================
class AuditorPanorama:
    def __init__(self):
        print(f"🎬 Iniciando Auditoría Panorámica (±10 Velas): {SYMBOL}")
        self._load()

    def _load(self):
        print("⏳ Preparando Timeframes...")
        df = pd.read_csv(DATA_FILE)
        df.columns = [c.lower().strip() for c in df.columns]
        if 'close' not in df.columns: df.columns = ['timestamp','open','high','low','close','volume'][:6]
        
        # Timestamp parsing seguro
        if df.iloc[0][0] > 1000000000000: df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        else: df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        self.df_1m = preparar_data(df)
        self.df_15m = preparar_data(self.df_1m.resample('15min', closed='right', label='right').agg(
            {'open':'first', 'high':'max', 'low':'min', 'close':'last'}).dropna())
        
        self.scanner = StructureScanner(self.df_15m)
        print(f"✅ Data Lista. Analizando {len(self.df_15m)} velas de 15m...")

    def _extraer_secuencia(self, ts):
        """Extrae la 'película' de indicadores ±10 velas"""
        if ts not in self.df_15m.index: return None
        
        idx_loc = self.df_15m.index.get_loc(ts)
        
        # Validar bordes
        if idx_loc < LOOKBACK or idx_loc > len(self.df_15m) - LOOKFORWARD - 1: return None
        
        secuencia = {}
        
        # Recorrer desde -10 hasta +10
        for i in range(-LOOKBACK, LOOKFORWARD + 1):
            row = self.df_15m.iloc[idx_loc + i]
            prefix = f"T{i:+d}" # Ej: T-10, T+0, T+5
            if i == 0: prefix = "T0"
            
            secuencia[f'{prefix}_RSI'] = row['rsi']
            secuencia[f'{prefix}_MACD'] = row['macd_hist']
            secuencia[f'{prefix}_Close'] = row['close']
            
        return secuencia

    def _clasificar_resultado(self, ts, entry_price, signal):
        # Mirar futuro en 1m (Alta resolución)
        window = self.df_1m.loc[ts:].iloc[1:TIME_LIMIT_MIN+1]
        if window.empty: return "NEUTRAL"
        
        if signal == 'LONG':
            max_p = window['high'].max()
            min_p = window['low'].min()
            mfe = (max_p - entry_price) / entry_price
            mae = (min_p - entry_price) / entry_price
        else:
            min_p = window['low'].min()
            max_p = window['high'].max()
            mfe = (entry_price - min_p) / entry_price
            mae = (entry_price - max_p) / entry_price
            
        if mfe >= TARGET_PROFIT and mae > MAX_LOSS: return "WINNER"
        if mae <= MAX_LOSS and mfe < TARGET_PROFIT: return "LOSER"
        return "NEUTRAL"

    def ejecutar(self):
        dataset = []
        
        for ts, row in self.df_15m.iterrows():
            # SEÑAL BASE (Muy amplia para capturar todo)
            rsi = row['rsi']
            fibo = self.scanner.get_fibo_dist(ts, row['close'])
            
            signal = None
            if rsi < 35 and fibo < 0.015: signal = 'LONG'
            elif rsi > 65 and fibo < 0.015: signal = 'SHORT'
            
            if not signal: continue
            
            # 1. Obtener Resultado Real
            resultado = self._clasificar_resultado(ts, row['close'], signal)
            if resultado == "NEUTRAL": continue # Ignoramos el ruido lateral
            
            # 2. Obtener Secuencia
            secuencia = self._extraer_secuencia(ts)
            if not secuencia: continue
            
            # 3. Guardar
            row_data = {
                'timestamp': ts,
                'signal': signal,
                'RESULT': resultado,
                'fibo_dist_T0': fibo,
                **secuencia
            }
            dataset.append(row_data)
            
        df_res = pd.DataFrame(dataset)
        fname = "Panorama_Report.csv"
        df_res.to_csv(os.path.join(os.path.dirname(__file__), fname), index=False)
        print("\n" + "="*50)
        print(f"✅ ANÁLISIS PANORÁMICO COMPLETADO")
        print(f"📊 Eventos Clasificados: {len(df_res)}")
        print(f"   Winners: {len(df_res[df_res['RESULT']=='WINNER'])}")
        print(f"   Losers:  {len(df_res[df_res['RESULT']=='LOSER'])}")
        print(f"📄 Reporte: {fname}")
        print("="*50)

if __name__ == "__main__":
    AuditorPanorama().ejecutar()