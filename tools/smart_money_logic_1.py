import numpy as np

class SmartMoneyLogic:
    """
    LÓGICA INSTITUCIONAL (SMC):
    Módulo especializado para cálculos de Fibonacci, validación de FVG
    y estructura de mercado avanzada.
    """
    
    @staticmethod
    def proyectar_target_fibonacci(swing_high, swing_low, trend_direction):
        """
        Calcula objetivos basados en extensiones de Fibonacci (1.618 y 2.618).
        Retorna: tp1, tp2, tp3
        """
        # Calcular la altura del impulso previo
        rango = abs(swing_high - swing_low)
        
        if rango == 0: return None
        
        if trend_direction == 'LONG':
            # Proyección hacia arriba desde el Swing High (Ruptura)
            tp1 = swing_high + (rango * 1.0)   # 100% Extensión (Movimiento medido)
            tp2 = swing_high + (rango * 1.618) # Golden Ratio
            tp3 = swing_high + (rango * 2.618) # Runner
            
        else: # SHORT
            # Proyección hacia abajo desde el Swing Low (Ruptura)
            tp1 = swing_low - (rango * 1.0)
            tp2 = swing_low - (rango * 1.618)
            tp3 = swing_low - (rango * 2.618)
            
        return {'tp1': tp1, 'tp2': tp2, 'tp3': tp3}

    @staticmethod
    def validar_fvg_con_obv(df_slice, fvg_type):
        """
        Verifica si el OBV apoya la dirección del FVG.
        """
        # Lógica simplificada: La pendiente del OBV debe coincidir
        if len(df_slice) < 5: return False
        
        obv_start = df_slice.iloc[0]['obv']
        obv_end = df_slice.iloc[-1]['obv']
        
        if fvg_type == 'BULLISH':
            return obv_end > obv_start # Volumen subiendo
        else:
            return obv_end < obv_start # Volumen bajando