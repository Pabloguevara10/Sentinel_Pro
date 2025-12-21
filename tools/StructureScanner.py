import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

class StructureScanner:
    """
    STRUCTURE SCANNER V2.0 (Institutional Concepts):
    Detecta Swing Highs/Lows, BOS (Break of Structure), 
    CHoCH (Change of Character) y Zonas de Oferta/Demanda.
    """
    
    def __init__(self, order=5):
        # Order: Cuántas velas a izq y der deben ser menores para considerar un High
        self.order = order 

    def analizar_estructura(self, df):
        """Retorna un dict con la estructura de mercado detectada."""
        if df is None or len(df) < 50: return None
        
        # 1. Detectar Pivots
        df['min'] = df.iloc[argrelextrema(df.low.values, np.less_equal, order=self.order)[0]]['low']
        df['max'] = df.iloc[argrelextrema(df.high.values, np.greater_equal, order=self.order)[0]]['high']
        
        # 2. Identificar el último Swing High y Swing Low CONFIRMADOS
        last_highs = df[df['max'].notnull()]
        last_lows = df[df['min'].notnull()]
        
        if last_highs.empty or last_lows.empty: return None
        
        # Últimos puntos estructurales
        sh = last_highs.iloc[-1]
        sl = last_lows.iloc[-1]
        
        # Puntos anteriores para contexto
        prev_sh = last_highs.iloc[-2] if len(last_highs) > 1 else sh
        prev_sl = last_lows.iloc[-2] if len(last_lows) > 1 else sl

        # 3. Determinar Tendencia Estructural
        trend = 'NEUTRAL'
        if sh['high'] > prev_sh['high'] and sl['low'] > prev_sl['low']:
            trend = 'BULLISH'
        elif sh['high'] < prev_sh['high'] and sl['low'] < prev_sl['low']:
            trend = 'BEARISH'
            
        # 4. Detectar Rupturas (BOS / CHoCH) en tiempo real
        # Usamos el precio actual vs los últimos puntos estructurales
        current_price = df.iloc[-1]['close']
        signal_structure = None
        
        # Lógica de Ruptura Alcista
        if current_price > sh['high']:
            # Si veníamos bajistas y rompemos el último alto -> CHoCH Bullish
            if trend == 'BEARISH': 
                signal_structure = 'CHOCH_BULLISH'
            else:
                signal_structure = 'BOS_BULLISH'
                
        # Lógica de Ruptura Bajista
        elif current_price < sl['low']:
            # Si veníamos alcistas y rompemos el último bajo -> CHoCH Bearish
            if trend == 'BULLISH':
                signal_structure = 'CHOCH_BEARISH'
            else:
                signal_structure = 'BOS_BEARISH'

        return {
            'trend': trend,
            'last_high': sh['high'],
            'last_low': sl['low'],
            'signal': signal_structure,
            'sh_index': sh.name, # Timestamp o Index
            'sl_index': sl.name
        }