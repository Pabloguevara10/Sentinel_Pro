from config.config import Config
from tools.precision_lab import PrecisionLab
import pandas as pd

class Brain:
    """
    DEPARTAMENTO DE ESTRATEGIA (Cerebro V10 - SNIPER):
    Implementa la lógica de 'Sniper Elite':
    1. Zonas Macro (1H) -> Identificadas por PrecisionLab
    2. Gatillo Micro (5m/15m) -> Confirmación de rechazo y RSI.
    """
    def __init__(self, config):
        self.cfg = config
        self.lab = PrecisionLab() # Instanciamos las herramientas
    
    def analizar_mercado(self, cache_dfs):
        """
        Orquesta el análisis multi-timeframe.
        Retorna señal si se alinean los planetas (Zona + Gatillo).
        """
        # Requerimos data de 1H y 5m (o 15m)
        if '1h' not in cache_dfs or '5m' not in cache_dfs:
            return None
            
        df_1h = cache_dfs['1h']
        df_5m = cache_dfs['5m']
        
        if df_1h.empty or df_5m.empty: return None

        # 1. DETECTAR ZONAS MACRO (1H)
        zonas = self.lab.detectar_zonas_macro(df_1h)
        if not zonas: return None
        
        # Precio actual (último cierre de 5m como referencia rápida)
        current_price = df_5m.iloc[-1]['close']
        
        # 2. VERIFICAR SI ESTAMOS EN ZONA
        zona_activa = None
        for z in zonas:
            # Margen de tolerancia (opcional, aquí estricto)
            if z['type'] == 'DEMANDA':
                # El precio está "dentro" o "cerca" del bloque de demanda
                if z['bottom'] <= current_price <= z['top'] * 1.002:
                    zona_activa = z
                    break
            elif z['type'] == 'OFERTA':
                # El precio está en bloque de oferta
                if z['bottom'] * 0.998 <= current_price <= z['top']:
                    zona_activa = z
                    break
        
        if not zona_activa: return None # No estamos en zona, no disparamos
        
        # 3. BUSCAR GATILLO (CONFIRMACIÓN)
        # Usamos la última vela cerrada de 5m
        vela_gatillo = df_5m.iloc[-2] # -1 es la actual en formación, -2 es la cerrada
        rsi_actual = vela_gatillo['rsi']
        
        analisis = self.lab.analizar_gatillo_vela(vela_gatillo, rsi_actual)
        
        if not analisis or not analisis['tipo']: return None
        
        # 4. ALINEACIÓN FINAL
        signal = None
        
        if zona_activa['type'] == 'DEMANDA' and analisis['tipo'] == 'POSIBLE_LONG':
            # Confirmamos Long en zona de Demanda con rechazo alcista
            signal = {
                'strategy': 'SNIPER_V10_DEMANDA',
                'side': 'LONG',
                'price': float(current_price),
                'strength': 'HIGH'
            }
            
        elif zona_activa['type'] == 'OFERTA' and analisis['tipo'] == 'POSIBLE_SHORT':
            # Confirmamos Short en zona de Oferta con rechazo bajista
            signal = {
                'strategy': 'SNIPER_V10_OFERTA',
                'side': 'SHORT',
                'price': float(current_price),
                'strength': 'HIGH'
            }
            
        return signal