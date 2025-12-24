# =============================================================================
# UBICACIÓN: logic/brain.py
# DESCRIPCIÓN: CEREBRO TRÍADA V15 (INTEGRAL & BUGFIX CONFIG)
# =============================================================================

from config.config import Config
from tools.precision_lab import PrecisionLab
from tools.StructureScanner import StructureScanner
import pandas as pd

class Brain:
<<<<<<< HEAD
    """
    CEREBRO HÍBRIDO (V13.5 - ECOSYSTEM CORE):
    Centraliza la inteligencia del Ecosistema V13 (Simulador) 
    y mantiene compatibilidad Legacy V12.
    """
    def __init__(self, config):
        self.cfg = config
        self.lab = PrecisionLab()
        self.scanner = StructureScanner(order=5) # Scanner Institucional
    
    def analizar_mercado(self, cache_dfs):
        """
        Orquestador principal de estrategias.
        Jerarquía: Swing V3 (Estructura) > Gamma V7 (Momentum)
        """
        signal = None
        
        # 1. MODO ECOSISTEMA (V13 - SIMULADOR)
        # ------------------------------------
        if self.cfg.ENABLE_ECO_SWING_V3:
            try:
                signal = self._analizar_eco_swing_v3(cache_dfs)
                if signal: return signal
            except Exception as e:
                print(f"⚠️ Error en Brain Swing V3: {e}")

        if self.cfg.ENABLE_ECO_GAMMA_V7:
            try:
                signal = self._analizar_eco_gamma_v7(cache_dfs)
                if signal: return signal
            except Exception as e:
                print(f"⚠️ Error en Brain Gamma V7: {e}")
                
        # 2. MODO LEGACY (V12 - RESPALDO)
        # ------------------------------------
        if getattr(self.cfg, 'ENABLE_LEGACY_SNIPER', False):
            # Aquí iría la llamada a _analizar_legacy_sniper si se reactiva
            pass
            
        return None

    # =========================================================================
    # LÓGICA ECOSISTEMA V13 (Simulador)
    # =========================================================================
    
    def _analizar_eco_gamma_v7(self, cache_dfs):
        """
        TRENDHUNTER GAMMA V7:
        Estrategia de Scalping Momentum (RSI Slope + ADX + Fibo Context).
        TF Principal: 5m/15m | Contexto: 1h
        """
        if '15m' not in cache_dfs or '1h' not in cache_dfs: return None
        df_15m = cache_dfs['15m']
        df_1h = cache_dfs['1h']
        
        if len(df_15m) < 20: return None
        
        # Datos Actuales
=======
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
>>>>>>> 4c4d97b (commit 24/12)
        row = df_15m.iloc[-1]
        
<<<<<<< HEAD
        # 1. Indicadores Core
        rsi_val, rsi_slope = self.lab.analizar_rsi_slope(df_15m)
        adx = row.get('adx', 0)
        atr = row.get('atr', 0)
        
        # 2. Contexto Macro (Filtro Fibo)
        dist_fibo = self.lab.obtener_contexto_fibo(df_1h, price)
        cfg_g = self.cfg.GammaConfig
        
        side = None
        mode = 'NORMAL'
        
        # --- LÓGICA DE GATILLO ---
        
        # LONG: Sobreventa + Giro rápido hacia arriba + Fuerza ADX aceptable
        # Filtro Fibo: No comprar si estamos muy extendidos arriba (dist > max)
        if rsi_val < 35 and rsi_slope > 2:
            if dist_fibo < cfg_g.FILTRO_DIST_FIBO_MAX:
                if adx > 20: # Tendencia presente
                    side = 'LONG'
            
            # Hedge (Contra-tendencia arriesgada)
            elif dist_fibo < -cfg_g.HEDGE_DIST_FIBO_MIN: # Muy extendido abajo
                side = 'LONG'; mode = 'HEDGE'

        # SHORT: Sobrecompra + Giro rápido hacia abajo
        elif rsi_val > 65 and rsi_slope < -2:
            if dist_fibo > -cfg_g.FILTRO_DIST_FIBO_MAX: # No muy extendido abajo
                if adx > 20:
                    side = 'SHORT'
                    
            # Hedge
            elif dist_fibo > cfg_g.HEDGE_DIST_FIBO_MIN: # Muy extendido arriba
                side = 'SHORT'; mode = 'HEDGE'
                
        if side:
            return {
                'strategy': 'GAMMA_V7',
                'side': side,
                'mode': mode,
                'price': price,
                'atr': atr, # Útil para SL dinámico
                'params': cfg_g # Pasamos la config para el Shooter
=======
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
>>>>>>> 4c4d97b (commit 24/12)
            }
        return None

    def _analizar_eco_swing_v3(self, cache_dfs):
<<<<<<< HEAD
        """
        SWINGHUNTER ALPHA V3:
        Estrategia Estructural (BOS/CHOCH + Zonas).
        TF Análisis: 1h/4h | Confirmación: 15m
        """
=======
>>>>>>> 4c4d97b (commit 24/12)
        if '1h' not in cache_dfs or '4h' not in cache_dfs: return None
        scanner_4h = self.scanners_cache.get('4h')
        if not scanner_4h: return None
        
        df_1h = cache_dfs['1h']
<<<<<<< HEAD
        df_4h = cache_dfs['4h']
        
        # 1. Análisis Estructural Macro (4H)
        struct_4h = self.scanner.analizar_estructura(df_4h)
        if not struct_4h: return None
        
        # 2. Análisis Estructural Micro (1H)
        struct_1h = self.scanner.analizar_estructura(df_1h)
        if not struct_1h: return None
        
        current_price = df_1h.iloc[-1]['close']
        atr = df_1h.iloc[-1].get('atr', 0)
        cfg_s = self.cfg.SwingConfig
        
        side = None
        mode = 'NORMAL'
        
        # --- LÓGICA DE GATILLO ESTRUCTURAL ---
        
        # ESCENARIO LONG:
        # A. Tendencia Macro Alcista Y Micro hace BOS Alcista (Continuación)
        # B. Tendencia Macro Bajista PERO Micro hace CHOCH Alcista (Reversión)
        
        if struct_1h['signal'] == 'BOS_BULLISH' and struct_4h['trend'] == 'BULLISH':
            side = 'LONG'; mode = 'SWING_TREND'
            
        elif struct_1h['signal'] == 'CHOCH_BULLISH':
            # Validación extra: RSI no saturado
            rsi_1h = df_1h.iloc[-1]['rsi']
            if rsi_1h < 70:
                side = 'LONG'; mode = 'SWING_REVERSAL'
        
        # ESCENARIO SHORT:
        if struct_1h['signal'] == 'BOS_BEARISH' and struct_4h['trend'] == 'BEARISH':
            side = 'SHORT'; mode = 'SWING_TREND'
            
        elif struct_1h['signal'] == 'CHOCH_BEARISH':
            rsi_1h = df_1h.iloc[-1]['rsi']
            if rsi_1h > 30:
                side = 'SHORT'; mode = 'SWING_REVERSAL'
                
        if side:
            return {
                'strategy': 'SWING_V3',
                'side': side,
                'mode': mode,
                'price': current_price,
                'atr': atr,
                'stop_ref': struct_1h['last_low'] if side == 'LONG' else struct_1h['last_high'],
                'params': cfg_s
=======
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
>>>>>>> 4c4d97b (commit 24/12)
            }
        
        return None