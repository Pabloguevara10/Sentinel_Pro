import pandas as pd
import numpy as np

class PrecisionLab:
    """
    LABORATORIO DE PRECISIÓN (V13.5 - FULL INDICATORS):
    Calcula: RSI, EMAs, MACD, Bandas Bollinger, ATR y ADX.
    """
    
    def calcular_indicadores_full(self, df):
        """Aplica todos los indicadores necesarios para el Ecosistema."""
        if df is None or df.empty: return df
        df = df.copy()
        
        # 1. BÁSICOS
        df['rsi'] = self._calcular_rsi(df['close'], 14)
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # 2. MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # 3. ATR (Volatilidad Absoluta)
        df['atr'] = self._calcular_atr(df, 14)
        
        # 4. ADX (Fuerza de Tendencia)
        df['adx'] = self._calcular_adx(df, 14)
        
        return df

    def analizar_rsi_slope(self, df, period=14):
        """Calcula el ángulo/pendiente del RSI."""
        if len(df) < period + 2: return 50.0, 0.0
        rsi = self._calcular_rsi(df['close'], period)
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2] # Slope de la vela cerrada anterior
        slope = current_rsi - prev_rsi
        return current_rsi, slope

    def obtener_contexto_fibo(self, df_macro, current_price):
        """Calcula distancia relativa a la EMA 200 (Proxy de Fibo dinámico)."""
        if df_macro.empty: return 0.0
        ema_200 = df_macro.iloc[-1]['ema_200']
        if pd.isna(ema_200): return 0.0
        distancia = (current_price - ema_200) / ema_200
        return distancia

    # --- MÉTODOS PRIVADOS DE CÁLCULO ---

    def _calcular_rsi(self, series, period):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _calcular_atr(self, df, period):
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = (high - close).abs()
        tr3 = (low - close).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def _calcular_adx(self, df, period):
        """Cálculo simplificado vectorial del ADX."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        
        tr = self._calcular_atr(df, 1) # TR de 1 periodo para normalizar
        
        plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / tr.ewm(alpha=1/period).mean())
        minus_di = 100 * (minus_dm.abs().ewm(alpha=1/period).mean() / tr.ewm(alpha=1/period).mean())
        
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.ewm(alpha=1/period).mean()
        return adx