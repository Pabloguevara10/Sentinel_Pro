# =============================================================================
# UBICACIÓN: tools/StructureScanner.py
# DESCRIPCIÓN: ESCÁNER ESTRUCTURAL INSTITUCIONAL (V1 + V2 FULL)
# =============================================================================

import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

class StructureScanner:
    """
    Herramienta unificada de análisis estructural.
    Capacidades:
    1. Detección de Fractales (Swings)
    2. Rupturas de Estructura (BOS/CHoCH)
    3. Contexto Fibonacci Dinámico
    4. Detección de Agotamiento (Onda 5)
    5. Confluencia con FVG (Fair Value Gaps)
    """
    
    def __init__(self, df=None, order=5, df_fvg=None):
        self.df = df
        self.order = order
        self.df_fvg = df_fvg
        self.pivots = {}

    # --- MÓDULO 1: ANÁLISIS DE RUPTURAS (SWING V3 COMPAT) ---
    def analizar_estructura(self, df):
        """Detecta tendencia y rupturas (BOS/CHoCH) para SwingHunter."""
        if df is None or len(df) < 50: return None
        
        # Copia local para cálculos independientes
        df_calc = df.copy()
        
        # Detectar extremos locales
        df_calc['min'] = df_calc.iloc[argrelextrema(df_calc.low.values, np.less_equal, order=self.order)[0]]['low']
        df_calc['max'] = df_calc.iloc[argrelextrema(df_calc.high.values, np.greater_equal, order=self.order)[0]]['high']
        
        last_highs = df_calc[df_calc['max'].notnull()]
        last_lows = df_calc[df_calc['min'].notnull()]
        
        if last_highs.empty or last_lows.empty: return None
        
        # Últimos puntos
        sh = last_highs.iloc[-1]
        sl = last_lows.iloc[-1]
        prev_sh = last_highs.iloc[-2] if len(last_highs) > 1 else sh
        prev_sl = last_lows.iloc[-2] if len(last_lows) > 1 else sl

        # Definir Tendencia
        trend = 'NEUTRAL'
        if sh['high'] > prev_sh['high'] and sl['low'] > prev_sl['low']: trend = 'BULLISH'
        elif sh['high'] < prev_sh['high'] and sl['low'] < prev_sl['low']: trend = 'BEARISH'
            
        current_price = df_calc.iloc[-1]['close']
        signal = None
        
        # Detección de señales
        if current_price > sh['high']:
            signal = 'CHOCH_BULLISH' if trend == 'BEARISH' else 'BOS_BULLISH'
        elif current_price < sl['low']:
            signal = 'CHOCH_BEARISH' if trend == 'BULLISH' else 'BOS_BEARISH'

        return {
            'trend': trend,
            'last_high': sh['high'],
            'last_low': sl['low'],
            'signal': signal,
            'sh_index': sh.name,
            'sl_index': sl.name
        }

    # --- MÓDULO 2: CONTEXTO FIBONACCI & INSTITUCIONAL (GAMMA V7 / SHADOW) ---
    def precompute(self):
        """Pre-calcula pivotes para análisis histórico."""
        if self.df is not None and not self.df.empty:
            self._find_pivots_v2()

    def _find_pivots_v2(self):
        """Método interno para encontrar pivotes en self.df"""
        max_idx = argrelextrema(self.df['high'].values, np.greater, order=self.order)[0]
        min_idx = argrelextrema(self.df['low'].values, np.less, order=self.order)[0]
        self.pivots['highs'] = self.df.iloc[max_idx]
        self.pivots['lows'] = self.df.iloc[min_idx]

    def get_fibonacci_context_by_price(self, current_price):
        """Calcula proximidad a niveles Fibo clave."""
        if self.df is None or 'highs' not in self.pivots: return None
        
        try:
            last_high = self.pivots['highs']['high'].iloc[-1]
            last_low = self.pivots['lows']['low'].iloc[-1]
        except: return None
        
        if last_high <= last_low: return None 
        
        # Niveles Clave
        diff = last_high - last_low
        fibs = {
            '0.0': last_low,
            '0.236': last_low + 0.236 * diff,
            '0.382': last_low + 0.382 * diff,
            '0.5': last_low + 0.5 * diff,
            '0.618': last_low + 0.618 * diff, # Golden Pocket
            '0.786': last_low + 0.786 * diff,
            '1.0': last_high
        }
        
        min_dist = float('inf')
        nearest_lvl = 0.0
        
        for price in fibs.values():
            dist = abs(current_price - price)
            if dist < min_dist: 
                min_dist = dist
                nearest_lvl = price
                
        return {
            'min_dist_pct': min_dist / current_price, 
            'nearest_level': nearest_lvl
        }

    # --- MÓDULO 3: HERRAMIENTAS AVANZADAS (RESTAURADAS) ---
    def detect_wave_5_exhaustion(self, current_idx):
        """
        Detecta divergencia RSI en máximos (Posible fin de Onda 5).
        Utilizado para validaciones de reversión extra-fuertes.
        """
        if self.df is None: return False
        try:
            slice_df = self.df.iloc[:current_idx+1]
            curr_price = slice_df.iloc[-1]['close']
            curr_rsi = slice_df.iloc[-1]['rsi']
            
            # Pivotes locales
            high_idx = argrelextrema(slice_df['high'].values, np.greater, order=self.order)[0]
            if len(high_idx) < 1: return False
            
            last_pivot_idx = high_idx[-1]
            last_pivot_high = slice_df.iloc[last_pivot_idx]['high']
            last_pivot_rsi = slice_df.iloc[last_pivot_idx]['rsi']
            
            # Divergencia Bajista: Precio hace nuevo alto, RSI no
            if curr_price > last_pivot_high and curr_rsi < last_pivot_rsi:
                return True
        except: pass
        return False

    def check_fvg_confluence(self, current_price, current_ts):
        """Verifica si el precio está dentro de un FVG sin mitigar."""
        if self.df_fvg is None: return None
        # Filtrar FVGs pasados
        valid_fvgs = self.df_fvg[self.df_fvg['timestamp'] < current_ts]
        for _, fvg in valid_fvgs.iterrows():
            if fvg['bottom'] <= current_price <= fvg['top']:
                return fvg['type'] # 'BULLISH' / 'BEARISH'
        return None