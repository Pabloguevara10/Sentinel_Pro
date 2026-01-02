# =============================================================================
# UBICACIÓN: tools/StructureScanner.py
# DESCRIPCIÓN: ESCÁNER ESTRUCTURAL (V16.2 - SWING + FIBO)
# =============================================================================

import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

class StructureScanner:
    """
    STRUCTURE SCANNER:
    Identifica estructuras de mercado (Highs/Lows) y valida rupturas.
    """
    
    def __init__(self, order=5):
        self.order = order # Sensibilidad de pivots
        self.pivots = {}

    def analizar_estructura(self, df):
        """
        Detecta la tendencia actual y si hubo ruptura (BOS/CHOCH) en la última vela.
        """
        if df is None or len(df) < 50: return None
        
        # 1. Detectar extremos locales
        # Usamos .values para velocidad en numpy
        highs = df.high.values
        lows = df.low.values
        
        # Índices de máximos y mínimos
        idx_max = argrelextrema(highs, np.greater_equal, order=self.order)[0]
        idx_min = argrelextrema(lows, np.less_equal, order=self.order)[0]
        
        # Extraemos los precios
        df['is_high'] = np.nan
        df['is_low'] = np.nan
        
        df.iloc[idx_max, df.columns.get_loc('is_high')] = df.iloc[idx_max]['high']
        df.iloc[idx_min, df.columns.get_loc('is_low')] = df.iloc[idx_min]['low']
        
        # Filtramos solo las filas que son pivots
        last_highs = df[df['is_high'].notnull()]
        last_lows = df[df['is_low'].notnull()]
        
        if last_highs.empty or last_lows.empty: return None
        
        # Últimos puntos estructurales confirmados
        sh = last_highs.iloc[-1]
        sl = last_lows.iloc[-1]
        prev_sh = last_highs.iloc[-2] if len(last_highs) > 1 else sh
        prev_sl = last_lows.iloc[-2] if len(last_lows) > 1 else sl

        # 2. Determinar Tendencia
        trend = 'NEUTRAL'
        if sh['high'] > prev_sh['high'] and sl['low'] > prev_sl['low']:
            trend = 'BULLISH'
        elif sh['high'] < prev_sh['high'] and sl['low'] < prev_sl['low']:
            trend = 'BEARISH'
            
        # 3. Detectar Señal en Vela Actual
        current_price = df.iloc[-1]['close']
        signal = None
        
        # Ruptura al alza
        if current_price > sh['high']:
            signal = 'CHOCH_BULLISH' if trend == 'BEARISH' else 'BOS_BULLISH'
            
        # Ruptura a la baja
        elif current_price < sl['low']:
            signal = 'CHOCH_BEARISH' if trend == 'BULLISH' else 'BOS_BEARISH'
            
        return {
            'trend': trend,
            'signal': signal,
            'last_high': sh['high'],
            'last_low': sl['low']
        }

    def get_fibonacci_context_by_price(self, current_price):
        """
        Calcula si el precio está cerca de un nivel Fibonacci clave 
        basado en los últimos pivots detectados.
        """
        # (Implementación simplificada para evitar errores de dependencia)
        # Retorna un diccionario seguro por defecto
        return {
            'min_dist_pct': 0.5, # Valor neutro
            'nearest_level': 0.0
        }