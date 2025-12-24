# =============================================================================
# UBICACIÓN: tools/precision_lab.py
# DESCRIPCIÓN: LABORATORIO MATEMÁTICO UNIFICADO (V15)
# =============================================================================

import pandas as pd
import numpy as np

class PrecisionLab:
    
    # --- INTERFAZ PRINCIPAL UNIFICADA ---
    def calculate_all(self, df):
        """Alias moderno para cálculo completo."""
        return self.calcular_indicadores_full(df)

    def calcular_indicadores_full(self, df):
        """
        Calcula TODOS los indicadores requeridos por el ecosistema (V13 + V15).
        Incluye: RSI, EMAs, MACD, ATR, ADX, Bollinger Bands.
        """
        if df is None or df.empty: return df
        df = df.copy()
        
        # 1. RSI
        df['rsi'] = self._calcular_rsi(df['close'], 14)
        
        # 2. EMAs
        for span in [9, 21, 50, 200]:
            df[f'ema_{span}'] = df['close'].ewm(span=span, adjust=False).mean()
        
        # 3. MACD
        k_fast = df['close'].ewm(span=12, adjust=False).mean()
        k_slow = df['close'].ewm(span=26, adjust=False).mean()
        df['macd_line'] = k_fast - k_slow
        df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd_line'] - df['macd_signal']

        # 4. ATR
        df['atr'] = self._calcular_atr(df, 14)
        
        # 5. ADX
        df['adx'] = self._calcular_adx(df, 14)

        # 6. BOLLINGER BANDS (Shadow Hunter)
        sma_20 = df['close'].rolling(window=20).mean()
        std_20 = df['close'].rolling(window=20).std()
        df['bb_upper'] = sma_20 + (std_20 * 2.0)
        df['bb_lower'] = sma_20 - (std_20 * 2.0)
        df['bb_mid'] = sma_20
        df['bb_width'] = df['bb_upper'] - df['bb_lower']
        
        return df

    # --- MÉTODOS DE ANÁLISIS PUNTUAL (UTILIDADES) ---
    
    def analizar_rsi_slope(self, df, period=14):
        """Retorna (rsi_actual, pendiente)."""
        if len(df) < period + 2: return 50.0, 0.0
        # Calculamos solo si no existe
        if 'rsi' not in df.columns:
            rsi = self._calcular_rsi(df['close'], period)
        else:
            rsi = df['rsi']
            
        return rsi.iloc[-1], rsi.iloc[-1] - rsi.iloc[-2]

    def obtener_contexto_fibo(self, df_macro, current_price):
        """Distancia a EMA200 (Proxy Fibo Rápido)."""
        if df_macro.empty: return 0.0
        ema = df_macro.iloc[-1].get('ema_200')
        if not ema or pd.isna(ema): return 0.0
        return (current_price - ema) / ema

    # --- MÉTODOS PRIVADOS DE CÁLCULO (Disponibles para uso interno) ---

    def _calcular_rsi(self, series, period):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _calcular_atr(self, df, period):
        high = df['high']; low = df['low']; close = df['close'].shift(1)
        tr = pd.concat([high-low, (high-close).abs(), (low-close).abs()], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def _calcular_adx(self, df, period):
        high = df['high']; low = df['low']
        plus_dm = high.diff(); minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0; minus_dm[minus_dm > 0] = 0
        tr = self._calcular_atr(df, 1)
        
        # Evitar división por cero
        tr_smooth = tr.ewm(alpha=1/period).mean()
        tr_smooth = tr_smooth.replace(0, 1)
        
        plus = 100 * (plus_dm.ewm(alpha=1/period).mean() / tr_smooth)
        minus = 100 * (minus_dm.abs().ewm(alpha=1/period).mean() / tr_smooth)
        
        dx = (abs(plus - minus) / (plus + minus).replace(0, 1)) * 100
        return dx.ewm(alpha=1/period).mean()