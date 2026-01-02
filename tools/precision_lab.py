# =============================================================================
# UBICACIÓN: tools/precision_lab.py
# DESCRIPCIÓN: LABORATORIO MATEMÁTICO (V16.2 - TRIAD READY)
# =============================================================================

import pandas as pd
import numpy as np

class PrecisionLab:
    """
    LABORATORIO DE PRECISIÓN:
    Calcula todos los indicadores técnicos necesarios para la Tríada:
    - Gamma: RSI, ADX, ATR
    - Shadow: Bandas de Bollinger
    - Swing: EMAs, MACD
    """
    
    def calculate_all(self, df):
        """Alias para integración rápida."""
        return self.calcular_indicadores_full(df)

    def calcular_indicadores_full(self, df):
        """
        Aplica indicadores vectorizados sobre el DataFrame.
        """
        if df is None or df.empty: return df
        df = df.copy()
        
        # 1. RSI (Momentum)
        df['rsi'] = self._calcular_rsi(df['close'], 14)
        
        # 2. EMAs (Tendencia)
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # 3. MACD (Confluencia)
        k_fast = df['close'].ewm(span=12, adjust=False).mean()
        k_slow = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = k_fast - k_slow
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # 4. ATR (Volatilidad)
        df['atr'] = self._calcular_atr(df, 14)
        
        # 5. ADX (Fuerza de Tendencia)
        df['adx'] = self._calcular_adx(df, 14)

        # 6. BANDAS DE BOLLINGER (Shadow Hunter)
        sma_20 = df['close'].rolling(window=20).mean()
        std_20 = df['close'].rolling(window=20).std()
        df['bb_upper'] = sma_20 + (std_20 * 2.0)
        df['bb_lower'] = sma_20 - (std_20 * 2.0)
        df['bb_mid'] = sma_20
        df['bb_width'] = df['bb_upper'] - df['bb_lower']
        
        return df

    # --- MÉTODOS DE ANÁLISIS ---

    def analizar_rsi_slope(self, df, period=14):
        """Devuelve el valor actual y la pendiente del RSI."""
        if len(df) < period + 2: return 50.0, 0.0
        
        if 'rsi' not in df.columns:
            series_rsi = self._calcular_rsi(df['close'], period)
        else:
            series_rsi = df['rsi']
            
        current = series_rsi.iloc[-1]
        prev = series_rsi.iloc[-2]
        slope = current - prev
        return current, slope

    def obtener_contexto_fibo(self, df_macro, current_price):
        """Usa EMA200 como proxy dinámico de nivel macro."""
        if df_macro.empty: return 0.0
        ema = df_macro.iloc[-1].get('ema_200')
        if not ema or pd.isna(ema): return 0.0
        
        distancia = (current_price - ema) / ema
        return distancia

    # --- CÁLCULOS INTERNOS ---

    def _calcular_rsi(self, series, period):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        # Manejo de división por cero
        rs = rs.replace([np.inf, -np.inf], 0).fillna(0)
        return 100 - (100 / (1 + rs))

    def _calcular_atr(self, df, period):
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = (high - close).abs()
        tr3 = (low - close).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def _calcular_adx(self, df, period):
        high = df['high']
        low = df['low']
        
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        
        tr = self._calcular_atr(df, 1)
        
        # Suavizado Wilder
        alpha = 1/period
        
        tr_smooth = tr.ewm(alpha=alpha, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=alpha, adjust=False).mean() / tr_smooth)
        minus_di = 100 * (minus_dm.abs().ewm(alpha=alpha, adjust=False).mean() / tr_smooth)
        
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.ewm(alpha=alpha, adjust=False).mean()
        return adx.fillna(0)