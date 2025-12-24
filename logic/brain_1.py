from config.config import Config
from tools.precision_lab import PrecisionLab
from tools.StructureScanner import StructureScanner
import pandas as pd

class Brain:
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
        row = df_15m.iloc[-1]
        price = row['close']
        
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
            }
        return None

    def _analizar_eco_swing_v3(self, cache_dfs):
        """
        SWINGHUNTER ALPHA V3:
        Estrategia Estructural (BOS/CHOCH + Zonas).
        TF Análisis: 1h/4h | Confirmación: 15m
        """
        if '1h' not in cache_dfs or '4h' not in cache_dfs: return None
        df_1h = cache_dfs['1h']
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
            }
        
        return None