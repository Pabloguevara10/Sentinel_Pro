from config.config import Config
from tools.precision_lab import PrecisionLab
import pandas as pd

class Brain:
    """
    DEPARTAMENTO DE ESTRATEGIA (Cerebro V11.5 - SELECTIVO):
    Capaz de encender o apagar estrategias según configuración global.
    Soporta:
    1. SNIPER V10: Zonas Macro 1H + Gatillo 5m (Alta Precisión).
    2. SCALPING GAMMA: Volatilidad 15m + Anti-Chasing (Alta Frecuencia).
    """
    def __init__(self, config):
        self.cfg = config
        self.lab = PrecisionLab()
    
    def analizar_mercado(self, cache_dfs):
        """
        Orquesta el análisis y selecciona la mejor señal disponible
        respetando los interruptores de configuración.
        """
        # 1. EVALUAR ESTRATEGIA SNIPER (Solo si el interruptor está ENCENDIDO)
        if getattr(self.cfg, 'ENABLE_STRATEGY_SNIPER', True):
            signal_sniper = self._analizar_sniper(cache_dfs)
            if signal_sniper:
                return signal_sniper
            
        # 2. EVALUAR ESTRATEGIA GAMMA (Solo si el interruptor está ENCENDIDO)
        if getattr(self.cfg, 'ENABLE_STRATEGY_GAMMA', True):
            signal_gamma = self._analizar_gamma(cache_dfs)
            if signal_gamma:
                return signal_gamma
            
        return None

    def _analizar_sniper(self, cache_dfs):
        if '1h' not in cache_dfs or '5m' not in cache_dfs: return None
        df_1h = cache_dfs['1h']
        df_5m = cache_dfs['5m']
        if df_1h.empty or df_5m.empty: return None

        # A. Detectar Zonas
        zonas = self.lab.detectar_zonas_macro(df_1h)
        if not zonas: return None
        
        current_price = df_5m.iloc[-1]['close']
        
        # B. Verificar Zona Activa
        zona_activa = None
        for z in zonas:
            if z['type'] == 'DEMANDA' and (z['bottom'] <= current_price <= z['top'] * 1.002):
                zona_activa = z; break
            elif z['type'] == 'OFERTA' and (z['bottom'] * 0.998 <= current_price <= z['top']):
                zona_activa = z; break
        
        if not zona_activa: return None
        
        # C. Gatillo
        vela_gatillo = df_5m.iloc[-2]
        rsi_actual = vela_gatillo.get('rsi', 50)
        analisis = self.lab.analizar_gatillo_vela(vela_gatillo, rsi_actual)
        
        if not analisis or not analisis['tipo']: return None
        
        # D. Confirmación
        if zona_activa['type'] == 'DEMANDA' and analisis['tipo'] == 'POSIBLE_LONG':
            return {'strategy': 'SNIPER_V10', 'side': 'LONG', 'price': float(current_price)}
        elif zona_activa['type'] == 'OFERTA' and analisis['tipo'] == 'POSIBLE_SHORT':
            return {'strategy': 'SNIPER_V10', 'side': 'SHORT', 'price': float(current_price)}
            
        return None

    def _analizar_gamma(self, cache_dfs):
        """
        Lógica Gamma: 15m RSI Slope + Anti-Chasing.
        """
        if '15m' not in cache_dfs: return None
        df_15m = cache_dfs['15m']
        if len(df_15m) < 5: return None
        
        curr_candle = df_15m.iloc[-1]
        prev_candle = df_15m.iloc[-2]
        
        # RSI Slope: Cambio del RSI en la última vela cerrada
        rsi_now = prev_candle.get('rsi', 50)
        rsi_prev = df_15m.iloc[-3].get('rsi', 50)
        rsi_slope = rsi_now - rsi_prev
        
        current_price = curr_candle['close']
        
        signal = None
        
        # Lógica Long
        if rsi_now < 30 and rsi_slope > 3:
            signal = {'strategy': 'SCALPING_GAMMA', 'side': 'LONG', 'price': float(current_price)}
            
        # Lógica Short
        elif rsi_now > 70 and rsi_slope < -3:
            # Filtro Anti-Chasing
            if rsi_slope < -15: # Caída extrema
                return None 
            signal = {'strategy': 'SCALPING_GAMMA', 'side': 'SHORT', 'price': float(current_price)}
            
        return signal