from config.config import Config
from tools.precision_lab import PrecisionLab
import pandas as pd

class Brain:
    """
    CEREBRO V13.1 (DUAL CORE MANAGER):
    Orquesta Gamma V7 y Swing V3.
    """
    def __init__(self, config):
        self.cfg = config
        self.lab = PrecisionLab()
    
    def analizar_mercado(self, cache_dfs):
        """Método principal llamado por el Bot."""
        # 1. Calcular indicadores necesarios para V13
        for tf in ['15m', '1h', '4h', '1d']:
            if tf in cache_dfs:
                cache_dfs[tf] = self.lab.calcular_indicadores_core(cache_dfs[tf])

        # 2. EVALUAR SWING V3 (Prioridad Jerárquica)
        if getattr(self.cfg, 'ENABLE_STRATEGY_SWING', False):
            signal_swing = self._analizar_swing(cache_dfs)
            if signal_swing: return signal_swing
            
        # 3. EVALUAR GAMMA V7 (Alta Frecuencia)
        if getattr(self.cfg, 'ENABLE_STRATEGY_GAMMA', True):
            signal_gamma = self._analizar_gamma(cache_dfs)
            if signal_gamma: return signal_gamma
            
        return None

    def _analizar_gamma(self, cache_dfs):
        """Lógica Gamma V7: Scalping Dual Core"""
        if '15m' not in cache_dfs or '1h' not in cache_dfs: return None
        df_15m = cache_dfs['15m']
        df_1h = cache_dfs['1h']
        if len(df_15m) < 15 or len(df_1h) < 50: return None
        
        row = df_15m.iloc[-1]
        price = row['close']
        
        rsi, slope = self.lab.analizar_rsi_slope(df_15m)
        macd = row['macd_hist']
        dist_fibo = self.lab.obtener_contexto_fibo(df_1h, price)
        
        cfg_g = self.cfg.GammaConfig
        side = None; mode = None
        
        if rsi < 30 and slope > 3: # Intención LONG
            if macd > cfg_g.FILTRO_MACD_MIN and dist_fibo < cfg_g.FILTRO_DIST_FIBO_MAX:
                side = 'LONG'; mode = 'GAMMA_NORMAL'
            elif macd < cfg_g.HEDGE_MACD_MAX and dist_fibo > cfg_g.HEDGE_DIST_FIBO_MIN:
                side = 'SHORT'; mode = 'GAMMA_HEDGE'

        elif rsi > 70 and slope < -3: # Intención SHORT
            if macd < -cfg_g.FILTRO_MACD_MIN and dist_fibo < cfg_g.FILTRO_DIST_FIBO_MAX:
                side = 'SHORT'; mode = 'GAMMA_NORMAL'
            elif macd > -cfg_g.HEDGE_MACD_MAX and dist_fibo > cfg_g.HEDGE_DIST_FIBO_MIN:
                side = 'LONG'; mode = 'GAMMA_HEDGE'

        if side:
            return {
                'strategy': 'GAMMA_V7',
                'side': side,
                'mode': mode,
                'price': price,
                'params': cfg_g # Configuración para Shooter
            }
        return None

    def _analizar_swing(self, cache_dfs):
        """Lógica Swing V3: Fractional Smart"""
        if '1h' not in cache_dfs or '4h' not in cache_dfs: return None
        df_1h = cache_dfs['1h']
        df_macro = cache_dfs['4h']
        if len(df_1h) < 15 or len(df_macro) < 50: return None
        
        row = df_1h.iloc[-1]
        price = row['close']
        rsi = row['rsi']
        macd = row['macd_hist']
        dist_macro = self.lab.obtener_contexto_fibo(df_macro, price)
        
        cfg_s = self.cfg.SwingConfig
        side = None; mode = None
        
        if rsi < 35: # Dip
            if macd > 0 and dist_macro < cfg_s.FILTRO_DIST_FIBO_MACRO:
                side = 'LONG'; mode = 'SWING_NORMAL'
            elif macd < cfg_s.HEDGE_MACD_MAX and dist_macro > cfg_s.HEDGE_DIST_FIBO_MIN:
                side = 'SHORT'; mode = 'SWING_HEDGE'
                
        elif rsi > 65: # Peak
            if macd < 0 and dist_macro < cfg_s.FILTRO_DIST_FIBO_MACRO:
                side = 'SHORT'; mode = 'SWING_NORMAL'
            elif macd > -cfg_s.HEDGE_MACD_MAX and dist_macro > cfg_s.HEDGE_DIST_FIBO_MIN:
                side = 'LONG'; mode = 'SWING_HEDGE'
                
        if side:
            return {
                'strategy': 'SWING_V3',
                'side': side,
                'mode': mode,
                'price': price,
                'params': cfg_s
            }
        return None