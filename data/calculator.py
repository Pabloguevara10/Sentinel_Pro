import pandas as pd
import numpy as np

class Calculator:
    """
    DEPARTAMENTO DE INVESTIGACIÓN (Área Matemática):
    Calcula indicadores técnicos.
    VERSION: ALFA1 (Agregado OBV y Pivotes Diarios)
    """
    
    @staticmethod
    def calcular_indicadores(df):
        if df is None or df.empty: return df
        df = df.copy()
        
        # Casting
        for c in ['open', 'high', 'low', 'close', 'volume']:
            df[c] = df[c].astype(float)

        # 1. OBV (On-Balance Volume) - NUEVO
        # Si el cierre es mayor al anterior, suma volumen. Si es menor, resta.
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()

        # 2. EMAs
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # 3. RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 4. Bollinger Bands
        sma = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std()
        df['bb_upper'] = sma + (std * 2)
        df['bb_middle'] = sma
        df['bb_lower'] = sma - (std * 2)

        # 5. ATR (Volatilidad para Stop Loss)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr'] = true_range.rolling(14).mean()

        # 6. Pivotes Diarios (Rolling 24h aproximado para intradía)
        # Nota: Para precisión exacta del PDH/PDL usamos el timeframe '1d' en el scanner
        # Aquí dejamos una referencia rolling para el corto plazo
        df['rolling_24h_high'] = df['high'].rolling(1440).max() # 1440 mins en un día (si es data 1m)
        df['rolling_24h_low'] = df['low'].rolling(1440).min()

        return df