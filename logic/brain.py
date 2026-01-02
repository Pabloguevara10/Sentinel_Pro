# =============================================================================
# UBICACIÓN: logic/brain.py
# DESCRIPCIÓN: CEREBRO TRÍADA V18 (GAMMA V4.6 + LEGACY SUPPORT)
# =============================================================================

from config.config import Config
from tools.StructureScanner_2 import StructureScanner
import pandas as pd
import pandas_ta as ta
import numpy as np

class Brain:
    """
    CEREBRO TRÍADA V18:
    - Gamma V4.6 (Lógica Activa Principal).
    - Swing V3 (Lógica Preservada).
    - Shadow V2 (Lógica Preservada).
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
        Analiza el mercado buscando señales en todas las estrategias activas.
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
        # Usamos StructureScanner_2 para obtener la data estructural
        self.scanners['1h'] = StructureScanner(df_1h)
        self.scanners['1h'].precompute()
        
        self.scanners['4h'] = StructureScanner(df_4h)
        self.scanners['4h'].precompute()

        # 3. Datos de la vela actual (15m)
        row_15m = df_15m.iloc[-1]
        
        # --- TIMESTAMP SAFEGUARD ---
        raw_ts = row_15m.get('timestamp')
        if raw_ts is None: raw_ts = row_15m.name 

        try:
            if isinstance(raw_ts, (int, float, np.integer, np.floating)):
                timestamp = pd.to_datetime(raw_ts, unit='ms')
            else:
                timestamp = pd.to_datetime(raw_ts)
        except Exception:
            timestamp = pd.Timestamp.now()

        # -------------------------------------
        # ESTRATEGIAS
        # -------------------------------------

        # 1. SWING V3 (Inicio de hora - Estructural)
        if timestamp.minute == 0: 
            sig_swing = self._check_swing(df_1h, self.scanners['4h'], df_4h, timestamp)
            if sig_swing: signals.append(sig_swing)

        # 2. GAMMA V4.6 (Scalping 15m - Lógica Nueva)
        sig_gamma = self._check_gamma_v4_6(row_15m, self.scanners['1h'], df_1h, timestamp)
        if sig_gamma: signals.append(sig_gamma)

        # 3. SHADOW V2 (Reversión - Bandas Bollinger)
        sig_shadow = self._check_shadow(row_15m, timestamp)
        if sig_shadow: signals.append(sig_shadow)

        return signals

    # =========================================================================
    # MOTORES LÓGICOS
    # =========================================================================

    def _get_dist(self, ts, scanner, df_context):
        """Calcula distancia al nivel Fibo más cercano (StructureScanner_2)."""
        try:
            idx = len(df_context) - 1
            ctx = scanner.get_fibonacci_context(idx)
            
            if not ctx or 'fibs' not in ctx: 
                return 999
            
            price = df_context.iloc[idx]['close']
            if price == 0: return 999
            
            return min([abs(price - l)/price for l in ctx['fibs'].values()])
        except:
            return 999

    def _check_gamma_v4_6(self, row, scanner_1h, df_1h, ts):
        """
        LÓGICA GAMMA V4.6 (Strict S/L 2% + 3-Stage Exit)
        """
        # 1. Distancia Estructural
        dist_1h = self._get_dist(ts, scanner_1h, df_1h)
        
        # 2. Indicadores 15m (Calculados en Calculator V18)
        macd = row.get('macd_hist', 0) 
        rsi = row.get('rsi', 50)
        
        signal = None
        mode = None
        cfg = self.cfg.GammaConfig
        
        # --- TRIGGERS ---
        
        # A) GAMMA NORMAL LONG
        if rsi < 30 and dist_1h < cfg.FILTRO_DIST_FIBO_MAX:
            signal = 'LONG'; mode = 'GAMMA_NORMAL'
            
        # B) GAMMA NORMAL SHORT
        elif rsi > 70 and dist_1h < cfg.FILTRO_DIST_FIBO_MAX:
            signal = 'SHORT'; mode = 'GAMMA_NORMAL'
            
        # C) GAMMA HEDGE SHORT (Sniper Logic)
        elif rsi < 25 and dist_1h > cfg.HEDGE_DIST_FIBO_MIN and macd < cfg.HEDGE_MACD_MAX:
            signal = 'SHORT'; mode = 'GAMMA_HEDGE'
            
        if signal:
            return {
                'strategy': 'GAMMA',
                'signal': signal,
                'mode': mode,
                'price': row['close'],
                'timestamp': ts,
                'confidence': 1.0
            }
        return None

    def _check_swing(self, df_1h, scanner_4h, df_4h, ts):
        """Lógica SwingHunter Alpha V3 (Preservada)."""
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
        """Lógica ShadowHunter V2 (Preservada)."""
        price = row['close']
        atr = row.get('atr', 0)
        upper = row.get('bb_upper', 999999)
        lower = row.get('bb_lower', 0)
        
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