# =============================================================================
# UBICACIÓN: logic/brain.py
# DESCRIPCIÓN: CEREBRO TRÍADA V17.9 (TIMESTAMP SAFEGUARD)
# =============================================================================

from config.config import Config
from tools.StructureScanner_2 import StructureScanner
import pandas as pd
import pandas_ta as ta
import numpy as np

class Brain:
    """
    CEREBRO TRÍADA:
    Integra las 3 lógicas del simulador Ecosystem_Triad_Sim_2.py
    adaptadas para operar en vivo con persistencia de scanners.
    """
    def __init__(self, config):
        self.cfg = config
        # Cache para scanners (evita recalcular todo cada ciclo)
        self.scanners = {
            '1h': None,
            '4h': None
        }

    def analizar_mercado(self, data_map):
        """
        data_map: Diccionario con DFs {'15m': df, '1h': df, '4h': df, ...}
        Retorna: Lista de señales (Signals).
        """
        signals = []
        
        # 1. Validar datos mínimos requeridos
        if not all(k in data_map for k in ['15m', '1h', '4h']):
            return []

        df_15m = data_map['15m']
        df_1h = data_map['1h']
        df_4h = data_map['4h']
        
        # Validar que no estén vacíos
        if df_15m.empty or df_1h.empty or df_4h.empty:
            return []

        # 2. Actualizar Scanners Contextuales (1H y 4H)
        # Instanciamos StructureScanner_2 con los datos actuales
        self.scanners['1h'] = StructureScanner(df_1h)
        self.scanners['1h'].precompute()
        
        self.scanners['4h'] = StructureScanner(df_4h)
        self.scanners['4h'].precompute()

        # 3. Datos de la vela actual (15m)
        row_15m = df_15m.iloc[-1]
        
        # --- FIX CRÍTICO TIMESTAMP (V17.9) ---
        # Extraemos el timestamp, ya sea del índice o de la columna
        raw_ts = row_15m.get('timestamp')
        if raw_ts is None:
            raw_ts = row_15m.name # Fallback al índice

        # Convertimos a Datetime Object seguro
        try:
            # Si es número (ms), convertimos. Si ya es fecha, lo dejamos.
            if isinstance(raw_ts, (int, float, np.integer, np.floating)):
                timestamp = pd.to_datetime(raw_ts, unit='ms')
            else:
                timestamp = pd.to_datetime(raw_ts)
        except Exception:
            # Fallback de emergencia si falla la conversión
            timestamp = pd.Timestamp.now()

        # -------------------------------------

        # --- ESTRATEGIA 1: SWING V3 (Inicio de hora) ---
        # Verificamos si es el primer ciclo de la hora (aprox)
        if timestamp.minute == 0: 
            sig_swing = self._check_swing(df_1h, self.scanners['4h'], df_4h, timestamp)
            if sig_swing: signals.append(sig_swing)

        # --- ESTRATEGIA 2: GAMMA V7 (Scalping 15m) ---
        sig_gamma = self._check_gamma(row_15m, self.scanners['1h'], df_1h, timestamp)
        if sig_gamma: signals.append(sig_gamma)

        # --- ESTRATEGIA 3: SHADOW V2 (Reversión) ---
        sig_shadow = self._check_shadow(row_15m, timestamp)
        if sig_shadow: signals.append(sig_shadow)

        return signals

    # =========================================================================
    # LÓGICAS ESPECÍFICAS (PORTED FROM SIMULATOR)
    # =========================================================================

    def _get_dist(self, ts, scanner, df_context):
        """Calcula distancia al nivel Fibo más cercano en el contexto dado."""
        # Simplificación para Live: Usamos la última vela del contexto disponible.
        idx = len(df_context) - 1
        ctx = scanner.get_fibonacci_context(idx)
        
        if not ctx or 'fibs' not in ctx: 
            return 999
            
        price = df_context.iloc[idx]['close']
        # Distancia mínima porcentual
        return min([abs(price - l)/price for l in ctx['fibs'].values()])

    def _check_gamma(self, row, scanner_1h, df_1h, ts):
        """Lógica TrendHunter Gamma V7"""
        # Distancia Fibo en 1H
        dist_1h = self._get_dist(ts, scanner_1h, df_1h)
        
        # Indicadores (Calculados previamente o en DataSeeder)
        macd = row.get('macd_hist', 0)
        rsi = row.get('rsi', 50)
        
        signal = None
        mode = None
        
        # Parametros Config
        cfg = self.cfg.GammaConfig
        
        # Lógica
        if rsi < 30 and dist_1h < cfg.FILTRO_DIST_FIBO_MAX:
            signal = 'LONG'; mode = 'GAMMA_NORMAL'
        elif rsi > 70 and dist_1h < cfg.FILTRO_DIST_FIBO_MAX:
            signal = 'SHORT'; mode = 'GAMMA_NORMAL'
        # Hedge Logic (Reversal Counter-Trend)
        elif rsi < 25 and dist_1h > cfg.HEDGE_DIST_FIBO_MIN and macd < cfg.HEDGE_MACD_MAX:
            signal = 'SHORT'; mode = 'GAMMA_HEDGE'
            
        if signal:
            return {
                'strategy': 'GAMMA',
                'signal': signal, # LONG/SHORT
                'mode': mode,
                'price': row['close'],
                'timestamp': ts,
                'confidence': 1.0
            }
        return None

    def _check_swing(self, df_1h, scanner_4h, df_4h, ts):
        """Lógica SwingHunter Alpha V3"""
        row_1h = df_1h.iloc[-1]
        dist_4h = self._get_dist(ts, scanner_4h, df_4h)
        
        cfg = self.cfg.SwingConfig
        
        if row_1h['rsi'] < 35 and dist_4h < cfg.FILTRO_DIST_FIBO_MACRO:
            return {
                'strategy': 'SWING',
                'signal': 'LONG',
                'mode': 'SWING_NORMAL',
                'price': row_1h['close'],
                'timestamp': ts,
                'confidence': 1.0
            }
        return None

    def _check_shadow(self, row, ts):
        """Lógica ShadowHunter V2 (Cascada Bollinger)"""
        price = row['close']
        atr = row.get('atr', 0)
        
        # Bandas
        upper = row.get('bb_upper', 999999)
        lower = row.get('bb_lower', 0)
        
        # Short Entry (Touch Upper Band)
        if row['high'] >= upper:
            return {
                'strategy': 'SHADOW',
                'signal': 'SHORT',
                'mode': 'SHADOW_GRID',
                'price': price,
                'timestamp': ts,
                'atr': atr, 
                'confidence': 0.9 
            }
            
        # Long Entry (Touch Lower Band)
        if row['low'] <= lower:
            return {
                'strategy': 'SHADOW',
                'signal': 'LONG',
                'mode': 'SHADOW_GRID',
                'price': price,
                'timestamp': ts,
                'atr': atr,
                'confidence': 0.9
            }
        return None