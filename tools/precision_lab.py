import pandas as pd
import pandas_ta as ta

class PrecisionLab:
    """
    LABORATORIO DE PRECISIÓN (Herramientas Matemáticas):
    Provee funciones de análisis técnico avanzado para que el Cerebro las consuma.
    VERSION: 11.3 (Fix: Bucle de detección cubre todo el rango de datos)
    """
    def __init__(self):
        pass

    def detectar_zonas_macro(self, df_1h):
        """
        Identifica Bloques de Órdenes (OB) en temporalidad H1.
        Retorna una lista de zonas activas.
        """
        zones = []
        if df_1h is None or len(df_1h) < 2: # Necesitamos al menos 2 velas para comparar
            return zones

        # FIX: Iniciamos desde 0 para no ignorar las primeras velas del array
        # Terminamos en len-1 para que 'i+1' no se salga del rango
        for i in range(0, len(df_1h) - 1):
            row = df_1h.iloc[i]
            next_row = df_1h.iloc[i+1]
            
            # 1. DEMANDA (Bullish) - Compra
            # Patrón: Vela bajista (roja) seguida de vela alcista explosiva
            if row['close'] < row['open']: # Vela roja
                # La siguiente vela rompe el máximo de la roja con su cierre
                if next_row['close'] > row['high']:
                    zones.append({
                        'type': 'DEMANDA',
                        'top': row['high'],
                        'bottom': row['low'],
                        'created_at': row['timestamp'] 
                    })
            
            # 2. OFERTA (Bearish) - Venta
            # Patrón: Vela alcista (verde) seguida de vela bajista explosiva
            elif row['close'] > row['open']: # Vela verde
                # La siguiente vela rompe el mínimo de la verde con su cierre
                if next_row['close'] < row['low']:
                    zones.append({
                        'type': 'OFERTA',
                        'top': row['high'],
                        'bottom': row['low'],
                        'created_at': row['timestamp']
                    })
        
        # Retornamos las últimas 5 zonas detectadas para mantener relevancia
        return zones[-5:]

    def evaluar_dinamica_rsi(self, serie_rsi, periodo=5):
        """Calcula la velocidad del RSI para detectar fuerza o agotamiento."""
        if len(serie_rsi) < periodo + 1: return 'NEUTRAL'
        
        recientes = serie_rsi.iloc[-periodo:]
        delta = recientes.iloc[-1] - recientes.iloc[0]
        velocidad = delta / periodo
        
        if velocidad > 2.0: return 'ALCISTA_FUERTE'
        elif velocidad > 0: return 'ALCISTA_DEBIL'
        elif velocidad < -2.0: return 'BAJISTA_FUERTE'
        elif velocidad < 0: return 'BAJISTA_DEBIL'
        return 'PLANO'

    def analizar_gatillo_vela(self, vela_actual, rsi_valor):
        """
        Analiza si una vela individual muestra rechazo (mecha larga) 
        y si el RSI está en zona de disparo.
        """
        open_p = vela_actual['open']
        close_p = vela_actual['close']
        high_p = vela_actual['high']
        low_p = vela_actual['low']
        
        total_len = high_p - low_p
        if total_len == 0: return None
        
        body_top = max(open_p, close_p)
        body_bottom = min(open_p, close_p)
        
        # Cálculo de Mechas (Wicks)
        wick_upper = high_p - body_top
        wick_lower = body_bottom - low_p
        
        # Regla del 40%: La mecha debe ser al menos el 40% del total de la vela
        # NOTA: Esto es estricto. Si no hay operaciones, reducir a 0.30 o 0.25
        rechazo_bajista = (wick_upper / total_len) > 0.40 
        rechazo_alcista = (wick_lower / total_len) > 0.40 
        
        signal = None
        
        if rechazo_alcista and rsi_valor < 60:
            signal = 'POSIBLE_LONG'
        elif rechazo_bajista and rsi_valor > 40:
            signal = 'POSIBLE_SHORT'
            
        return {
            'tipo': signal,
            'rechazo_alcista': rechazo_alcista,
            'rechazo_bajista': rechazo_bajista
        }

    def detectar_divergencias(self, df, window=10):
        # Placeholder para futuro desarrollo
        return False