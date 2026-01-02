# =============================================================================
# UBICACIÓN: data/calculator.py
# DESCRIPCIÓN: CALCULADORA CIENTÍFICA V18.2 (FIX BB WIDTH DINÁMICO)
# =============================================================================

import pandas as pd
import pandas_ta as ta 
import numpy as np
import os

class Calculator:
    """
    CALCULADORA CIENTÍFICA (V18.2):
    - Core: Procesa datos para el Brain.
    - Visual: Genera Matriz Dashboard.
    - Fix: Detección dinámica de columnas Bollinger para evitar 0.00%.
    """
    
    @staticmethod
    def resample_data(df_1m, timeframe):
        """Convierte 1m -> TF Destino."""
        rule_map = {
            '1m': '1min', '2m': '2min', '3m': '3min', '5m': '5min', 
            '15m': '15min', '30m': '30min', '1h': '1h', '4h': '4h', '1d': '1D'
        }
        
        rule = rule_map.get(timeframe)
        if not rule: return None
        
        agg_dict = {
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last',
            'volume': 'sum', 'timestamp': 'first'
        }
        
        try:
            df_resampled = df_1m.resample(rule).agg(agg_dict).dropna()
            return df_resampled
        except Exception:
            return None

    @staticmethod
    def agregar_indicadores(df):
        """[CORE] Indicadores para la ESTRATEGIA (Brain)."""
        df = df.copy()
        
        # RSI (14)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rs = rs.replace([float('inf'), -float('inf')], 0).fillna(0)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # EMAs
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # MACD (12, 26, 9)
        k_fast = df['close'].ewm(span=12, adjust=False).mean()
        k_slow = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = k_fast - k_slow
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        df.bfill(inplace=True)
        return df

    # =========================================================================
    # MOTOR DE MATRIZ VISUAL (DASHBOARD)
    # =========================================================================

    @classmethod
    def generar_matriz_dashboard(cls, symbol, data_dir):
        resultados = {}
        tfs_visuales = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d']
        
        file_path = os.path.join(data_dir, f"{symbol}_1m.csv")
        if not os.path.exists(file_path): return {}

        try:
            df_master = pd.read_csv(file_path)
            df_master['datetime'] = pd.to_datetime(df_master['timestamp'], unit='ms')
            df_master.set_index('datetime', inplace=True)
        except: return {}

        for tf in tfs_visuales:
            try:
                if tf == '1m':
                    df_tf = df_master.copy()
                else:
                    df_tf = cls.resample_data(df_master, tf)
                
                if df_tf is None or df_tf.empty: continue

                df_ind = cls._calcular_indicadores_visuales_full(df_tf)
                last_row = df_ind.iloc[-1]
                
                resultados[tf] = {
                    'rsi': last_row.get('rsi', 50),
                    'adx': last_row.get('adx', 0),
                    'macd_hist': last_row.get('macd_hist', 0),
                    'stoch_k': last_row.get('stoch_k', 50),
                    'bb_width': last_row.get('bb_width', 0), # Ahora sí vendrá lleno
                    'vol_change': cls._calc_vol_change(df_tf),
                    'trend': cls._calc_trend_score(last_row)
                }
            except Exception: continue
                
        return resultados

    @staticmethod
    def _calcular_indicadores_visuales_full(df):
        """
        Calcula indicadores visuales de forma robusta.
        """
        df = df.copy()
        
        # 1. RSI
        df.ta.rsi(length=14, append=True)
        if 'RSI_14' in df.columns: df['rsi'] = df['RSI_14']
        
        # 2. MACD
        df.ta.macd(append=True)
        if 'MACDh_12_26_9' in df.columns: df['macd_hist'] = df['MACDh_12_26_9']
        
        # 3. ADX
        try:
            df.ta.adx(length=14, append=True)
            if 'ADX_14' in df.columns: df['adx'] = df['ADX_14']
        except: df['adx'] = 0

        # 4. BOLLINGER BANDS (FIX ROBUSTO)
        # Calculamos en un DF separado para inspeccionar columnas
        try:
            bb = df.ta.bbands(length=20, std=2)
            if bb is not None:
                # Concatenamos
                df = pd.concat([df, bb], axis=1)
                
                # Buscamos dinámicamente cualquier columna que empiece por 'BBB' (Bandwidth)
                # Esto soluciona el error de "BBB_20_2.0" vs "BBB_20_2"
                bbb_cols = [c for c in bb.columns if c.startswith('BBB')]
                if bbb_cols:
                    df['bb_width'] = df[bbb_cols[0]]
                else:
                    df['bb_width'] = 0
        except: df['bb_width'] = 0
        
        # 5. Stoch RSI
        try:
            df.ta.stochrsi(length=14, append=True)
            if 'STOCHRSIk_14_14_3_3' in df.columns: df['stoch_k'] = df['STOCHRSIk_14_14_3_3']
        except: df['stoch_k'] = 50

        return df

    @staticmethod
    def _calc_vol_change(df):
        if len(df) < 21: return "EQ"
        vol_ma = df['volume'].rolling(20).mean().iloc[-1]
        curr_vol = df['volume'].iloc[-1]
        if curr_vol > vol_ma * 1.1: return "UP"
        if curr_vol < vol_ma * 0.9: return "DN"
        return "EQ"

    @staticmethod
    def _calc_trend_score(row):
        macd = row.get('macd_hist', 0)
        rsi = row.get('rsi', 50)
        if macd > 0 and rsi > 45: return 1  # Bullish
        if macd < 0 and rsi < 55: return -1 # Bearish
        return 0