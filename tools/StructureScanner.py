import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

class StructureScanner:
    """
    Herramienta de Análisis Estructural para el Ecosistema de Trading.
    Ubicación: tools/StructureScanner.py
    Funciones:
    - Detección de Fractales/Pivotes (Swings).
    - Cálculo dinámico de Retrocesos y Extensiones de Fibonacci.
    - Detección de Divergencias (Posible Onda 5).
    - Lectura y validación de zonas FVG externas.
    """
    
    def __init__(self, df_prices, df_fvg=None):
        """
        :param df_prices: DataFrame con columnas [high, low, close, rsi, timestamp]
        :param df_fvg: DataFrame opcional con datos de FVG cargados desde data/historical/mapas_fvg
        """
        self.df = df_prices.copy()
        self.df_fvg = df_fvg
        
        # Parámetros configurables
        self.swing_window = 5 # Velas a izquierda/derecha para confirmar un pivote
    
    def _find_pivots(self):
        """Detecta Swing Highs y Swing Lows usando ventanas locales."""
        # Nota: Usamos argrelextrema para encontrar picos locales
        # order=5 significa que debe ser el máximo de 5 velas a cada lado
        self.df['is_pivot_high'] = False
        self.df['is_pivot_low'] = False
        
        high_idx = argrelextrema(self.df['high'].values, np.greater, order=self.swing_window)[0]
        low_idx = argrelextrema(self.df['low'].values, np.less, order=self.swing_window)[0]
        
        self.df.iloc[high_idx, self.df.columns.get_loc('is_pivot_high')] = True
        self.df.iloc[low_idx, self.df.columns.get_loc('is_pivot_low')] = True
        
        return self.df[self.df['is_pivot_high']], self.df[self.df['is_pivot_low']]

    def get_fibonacci_context(self, current_idx, lookback=100):
        """
        Analiza el último impulso relevante antes de la vela actual y calcula niveles.
        :return: Dict con niveles y estado.
        """
        # Recortar datos hasta el momento actual (simulación realista)
        # Asumimos que current_idx es el índice posicional (int)
        slice_df = self.df.iloc[max(0, current_idx - lookback) : current_idx + 1].copy()
        
        # Encontrar últimos pivotes en este slice
        highs = slice_df[slice_df['is_pivot_high']]
        lows = slice_df[slice_df['is_pivot_low']]
        
        if highs.empty or lows.empty:
            return None

        last_high = highs.iloc[-1]
        last_low = lows.iloc[-1]
        
        # Determinar dirección del último impulso mayor
        # Si el último High es más reciente que el último Low -> Impulso Alcista (ahora corrigiendo)
        # Si el último Low es más reciente que el último High -> Impulso Bajista (ahora rebotando)
        
        mode = 'UNKNOWN'
        fib_levels = {}
        
        if last_high.name > last_low.name: # Impulso Alcista previo
            mode = 'UP_IMPULSE_RETRACING'
            p_top = last_high['high']
            p_bot = last_low['low'] # Buscamos el low anterior al high
            
            # Buscar el low real del impulso (el low más bajo entre el high previo y el actual)
            # Simplificación: usaremos el último low detectado
            diff = p_top - p_bot
            fib_levels = {
                '0.0': p_top,
                '0.236': p_top - (diff * 0.236),
                '0.382': p_top - (diff * 0.382),
                '0.5': p_top - (diff * 0.5),
                '0.618': p_top - (diff * 0.618), # Golden Pocket
                '0.786': p_top - (diff * 0.786),
                '1.0': p_bot
            }
            
        else: # Impulso Bajista previo
            mode = 'DOWN_IMPULSE_BOUNCING'
            p_bot = last_low['low']
            p_top = last_high['high']
            
            diff = p_top - p_bot
            fib_levels = {
                '0.0': p_bot,
                '0.236': p_bot + (diff * 0.236),
                '0.382': p_bot + (diff * 0.382),
                '0.5': p_bot + (diff * 0.5),
                '0.618': p_bot + (diff * 0.618), # Golden Pocket
                '0.786': p_bot + (diff * 0.786),
                '1.0': p_top
            }

        return {
            'mode': mode,
            'top_price': p_top,
            'bottom_price': p_bot,
            'fibs': fib_levels
        }

    def detect_wave_5_exhaustion(self, current_idx):
        """
        Detecta si estamos potencialmente en una Onda 5 (Agotamiento).
        Lógica: Precio hace nuevo máximo pero RSI hace máximo menor (Divergencia).
        """
        slice_df = self.df.iloc[:current_idx+1]
        curr_price = slice_df.iloc[-1]['close']
        curr_rsi = slice_df.iloc[-1]['rsi']
        
        # Buscar el pivote High anterior
        highs = slice_df[slice_df['is_pivot_high']]
        if len(highs) < 2: return False
        
        last_pivot = highs.iloc[-1]
        
        # Si el precio actual es mayor que el último pivote High...
        if curr_price > last_pivot['high']:
            # ...pero el RSI actual es MENOR que el RSI de ese pivote
            if curr_rsi < last_pivot['rsi']:
                return True # DIVERGENCIA BAJISTA (Posible Fin Onda 5)
                
        return False

    def check_fvg_confluence(self, current_price, current_ts):
        """Verifica si el precio actual está dentro de un FVG válido."""
        if self.df_fvg is None: return None
        
        # Filtrar FVGs creados antes de la vela actual y NO mitigados (simplificado)
        valid_fvgs = self.df_fvg[self.df_fvg['timestamp'] < current_ts]
        
        for _, fvg in valid_fvgs.iterrows():
            if fvg['bottom'] <= current_price <= fvg['top']:
                return fvg['type'] # 'BULLISH' o 'BEARISH'
        
        return None

    def precompute(self):
        """Ejecutar al inicio para calcular pivotes en todo el histórico."""
        self._find_pivots()