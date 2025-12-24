# =============================================================================
# UBICACIÓN: logic/brain.py
# DESCRIPCIÓN: CEREBRO TRÍADA V15 (INTEGRAL & BUGFIX CONFIG)
# =============================================================================

from config.config import Config
from tools.precision_lab import PrecisionLab
from tools.StructureScanner import StructureScanner
import pandas as pd

class Brain:
    def __init__(self, config=Config):
        self.cfg = config
        self.lab = PrecisionLab()
        self.scanner = StructureScanner(df=None) # Inicialización genérica
        self.scanners_cache = {}

    def _update_scanners(self, dfs):
        """Actualiza caché de scanners estructurales."""
        try:
            for tf in ['1h', '4h', '1d']:
                if tf in dfs and not dfs[tf].empty:
                    self.scanners_cache[tf] = StructureScanner(dfs[tf])
                    self.scanners_cache[tf].precompute()
        except: pass

    def analizar_mercado(self, cache_dfs):
        signals = []
        self._update_scanners(cache_dfs)
        
        # Pre-cálculo de indicadores V15
        if '15m' in cache_dfs:
            cache_dfs['15m'] = self.lab.calculate_all(cache_dfs['15m'])

        # 1. SHADOW HUNTER V2
        if self.cfg.ENABLE_SHADOW_V2:
            try:
                sig = self._analizar_shadow_v2(cache_dfs)
                if sig: signals.append(sig)
            except Exception as e:
                print(f"Brain Shadow Error: {e}")

        # 2. SWING HUNTER V3
        if self.cfg.ENABLE_ECO_SWING_V3:
            try:
                sig = self._analizar_eco_swing_v3(cache_dfs)
                if sig: signals.append(sig)
            except Exception as e:
                print(f"Brain Swing Error: {e}")

        # 3. GAMMA V7
        if self.cfg.ENABLE_ECO_GAMMA_V7:
            try:
                sig = self._analizar_eco_gamma_v7(cache_dfs)
                if sig: signals.append(sig)
            except Exception as e:
                print(f"Brain Gamma Error: {e}")

        return signals if signals else None

    # --- ESTRATEGIAS ---

    def _analizar_shadow_v2(self, cache_dfs):
        if '15m' not in cache_dfs: return None
        df = cache_dfs['15m']
        if len(df) < 20: return None
        row = df.iloc[-1]
        
        upper = row.get('bb_upper'); lower = row.get('bb_lower')
        if not upper: return None
        
        side = None
        if row['high'] >= upper: side = 'SHORT'
        elif row['low'] <= lower: side = 'LONG'
        
        if side:
            return {
                'strategy': 'SHADOW_V2', 'mode': 'CASCADING', 'side': side,
                'price': row['close'], 'atr': row.get('atr', 0),
                'params': self.cfg.ShadowConfig
            }
        return None

    def _analizar_eco_gamma_v7(self, cache_dfs):
        if '15m' not in cache_dfs or '1h' not in cache_dfs: return None
        df_15m = cache_dfs['15m']
        row = df_15m.iloc[-1]
        
        scanner_1h = self.scanners_cache.get('1h')
        if not scanner_1h: return None
        ctx = scanner_1h.get_fibonacci_context_by_price(row['close'])
        if not ctx: return None
        
        cfg = self.cfg.GammaConfig # FIX REFERENCIA
        dist = ctx['min_dist_pct']
        
        rsi = row.get('rsi', 50)
        macd = row.get('macd_hist', 0)
        prev_rsi = df_15m.iloc[-2].get('rsi', 50)
        slope = rsi - prev_rsi
        
        side = None; mode = 'NORMAL'
        
        if rsi < 30 and slope > 2:
            if macd > cfg.FILTRO_MACD_MIN and dist < cfg.FILTRO_DIST_FIBO_MAX:
                side = 'LONG'
            elif macd < cfg.HEDGE_MACD_MAX and dist > cfg.HEDGE_DIST_FIBO_MIN:
                side = 'SHORT'; mode = 'GAMMA_HEDGE'
                
        elif rsi > 70 and slope < -2:
            if macd < -cfg.FILTRO_MACD_MIN and dist < cfg.FILTRO_DIST_FIBO_MAX:
                side = 'SHORT'
            elif macd > -cfg.HEDGE_MACD_MAX and dist > cfg.HEDGE_DIST_FIBO_MIN:
                side = 'LONG'; mode = 'GAMMA_HEDGE'
                
        if side:
            return {
                'strategy': 'GAMMA', 'side': side, 'mode': mode,
                'price': row['close'], 'atr': row.get('atr', 0),
                'params': cfg
            }
        return None

    def _analizar_eco_swing_v3(self, cache_dfs):
        if '1h' not in cache_dfs or '4h' not in cache_dfs: return None
        scanner_4h = self.scanners_cache.get('4h')
        if not scanner_4h: return None
        
        df_1h = cache_dfs['1h']
        row = df_1h.iloc[-1]
        
        ctx = scanner_4h.get_fibonacci_context_by_price(row['close'])
        dist = ctx['min_dist_pct'] if ctx else 999
        
        cfg = self.cfg.SwingConfig # FIX REFERENCIA
        
        side = None
        if row.get('rsi', 50) < 35 and row.get('macd_hist', 0) > 0 and dist < cfg.FILTRO_DIST_FIBO_MACRO:
            side = 'LONG'
        elif row.get('rsi', 50) > 65 and row.get('macd_hist', 0) < 0 and dist < cfg.FILTRO_DIST_FIBO_MACRO:
            side = 'SHORT'
            
        if side:
            return {
                'strategy': 'SWING', 'side': side, 'mode': 'SWING_NORMAL',
                'price': row['close'], 'atr': row.get('atr', 0),
                'stop_ref': ctx['nearest_level'] if ctx else 0,
                'params': cfg
            }
        return None