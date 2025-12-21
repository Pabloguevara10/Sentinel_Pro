import pandas as pd
import pandas_ta as ta
import numpy as np

class PrecisionLab:
    """
    LABORATORIO DE PRECISIÓN (V13.1 FUSIONADO):
    Contiene herramientas V13 (Dual Core) y Legacy (para compatibilidad).
    """
    def __init__(self):
        pass

    # --- NUEVAS HERRAMIENTAS V13 (GAMMA/SWING) ---

    def calcular_indicadores_core(self, df):
        """Calcula RSI y MACD necesarios para V13."""
        if df is None or len(df) < 30: return df
        
        # RSI
        df['rsi'] = ta.rsi(df['close'], length=14)
        
        # MACD (12, 26, 9)
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            # Pandas TA devuelve columnas con nombres específicos. 
            # La segunda columna suele ser el histograma (MACDh)
            df['macd_hist'] = macd.iloc[:, 1] 
        else:
            df['macd_hist'] = 0.0
            
        return df

    def obtener_contexto_fibo(self, df_macro, precio_actual):
        """Calcula distancia a soportes/resistencias recientes."""
        if df_macro is None or len(df_macro) < 50:
            return 999.0

        # Pivotes simples de 20 periodos
        highs = df_macro['high'].rolling(20).max()
        lows = df_macro['low'].rolling(20).min()
        
        ultimo_soporte = lows.iloc[-1] if not pd.isna(lows.iloc[-1]) else df_macro['low'].min()
        ultima_resistencia = highs.iloc[-1] if not pd.isna(highs.iloc[-1]) else df_macro['high'].max()
        
        dist_soporte = abs(precio_actual - ultimo_soporte) / precio_actual
        dist_resistencia = abs(precio_actual - ultima_resistencia) / precio_actual
        
        return min(dist_soporte, dist_resistencia)

    def analizar_rsi_slope(self, df, period=14):
        """Retorna valor y pendiente del RSI."""
        if len(df) < 3: return 50, 0
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
        
        rsi_now = curr.get('rsi', 50)
        rsi_prev_confirmed = prev.get('rsi', 50)
        rsi_old = prev_prev.get('rsi', 50)
        
        slope = rsi_prev_confirmed - rsi_old
        return rsi_now, slope

    # --- HERRAMIENTAS LEGACY (RESTAURADAS POR SEGURIDAD) ---

    def detectar_zonas_macro(self, df_1h):
        """(Legacy) Identifica Bloques de Órdenes simples."""
        zones = []
        if df_1h is None or len(df_1h) < 2: return zones
        for i in range(0, len(df_1h) - 1):
            row = df_1h.iloc[i]
            next_row = df_1h.iloc[i+1]
            if row['close'] < row['open'] and next_row['close'] > next_row['open']:
                if next_row['close'] > row['high']:
                    zones.append({'type': 'DEMANDA', 'price': row['low'], 'strength': 1})
            elif row['close'] > row['open'] and next_row['close'] < next_row['open']:
                if next_row['close'] < row['low']:
                    zones.append({'type': 'OFERTA', 'price': row['high'], 'strength': 1})
        return zones[-5:] # Retornar últimas 5

    def analizar_gatillo_vela(self, vela_actual, rsi_valor):
        """(Legacy) Análisis de mechas."""
        open_p = vela_actual['open']; close_p = vela_actual['close']
        high_p = vela_actual['high']; low_p = vela_actual['low']
        total_len = high_p - low_p
        if total_len == 0: return None
        
        body_top = max(open_p, close_p)
        wick_upper = high_p - body_top
        
        if (wick_upper / total_len) > 0.40 and rsi_valor > 60:
            return 'POSIBLE_SHORT'
        return None