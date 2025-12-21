import pandas as pd
import pandas_ta as ta 

class Calculator:
    """
    CALCULADORA CIENTÍFICA (V12.2 - PANDAS 2.0 COMPATIBLE):
    - Convierte 1m -> Temporalidades Superiores.
    - Calcula Indicadores Técnicos sin warnings de depreciación.
    """
    
    @staticmethod
    def resample_data(df_1m, timeframe):
        """
        Toma el DataFrame de 1m (con índice datetime) y lo convierte al TF destino.
        """
        # Mapeo de string '15m', '1h' a reglas de Pandas
        # CORRECCIÓN: Usamos 'h' minúscula en lugar de 'H' (Pandas 2.2+)
        rule_map = {
            '3m': '3min', '5m': '5min', '15m': '15min', '30m': '30min',
            '1h': '1h', '4h': '4h', '1d': '1D'
        }
        
        rule = rule_map.get(timeframe)
        if not rule: return None
        
        # Lógica de Agregación OHLCV
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'timestamp': 'first' # Mantenemos el timestamp de apertura
        }
        
        try:
            df_resampled = df_1m.resample(rule).agg(agg_dict).dropna()
            return df_resampled
        except Exception:
            return None

    @staticmethod
    def agregar_indicadores(df):
        """
        Agrega los indicadores técnicos básicos al DataFrame.
        """
        df = df.copy()
        
        # RSI (14)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # EMAs (9, 21, 50, 200)
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # Rellena NaN iniciales para no romper el scanner
        # CORRECCIÓN: Usamos bfill() directo en lugar de fillna(method='bfill')
        df.bfill(inplace=True)
        
        return df