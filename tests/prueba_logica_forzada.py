import pandas as pd
import sys
import os

# Ajuste de rutas para importar módulos del sistema principal
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.precision_lab import PrecisionLab
from logic.brain import Brain
from config.config import Config

def correr_prueba_concepto():
    print("\n🧪 --- INICIANDO PRUEBA DE CONCEPTO (DATA SINTÉTICA) ---")
    
    lab = PrecisionLab()
    brain = Brain(Config())

    # 1. CREAMOS UN ESCENARIO DE 1 HORA (PERFECTO)
    print("1. Generando Patrón Macro (1H)...")
    datos_1h = [
        # Vela 0: Relleno inicial
        {'timestamp': 1000, 'open': 100, 'high': 105, 'low': 95, 'close': 100}, 
        # Vela 1: VELA ROJA (Base) - Aquí empieza el patrón
        {'timestamp': 2000, 'open': 100, 'high': 100, 'low': 90, 'close': 92},  
        # Vela 2: VELA VERDE (Rompe el high 100) -> ZONA CREADA
        {'timestamp': 3000, 'open': 92,  'high': 108, 'low': 92, 'close': 105}, 
        # Velas posteriores
        {'timestamp': 4000, 'open': 105, 'high': 106, 'low': 104,'close': 105}, 
        {'timestamp': 5000, 'open': 105, 'high': 106, 'low': 104,'close': 105}  
    ]
    df_1h = pd.DataFrame(datos_1h)
    
    # Prueba del Lab: ¿Ve la zona en el índice 1-2?
    zonas = lab.detectar_zonas_macro(df_1h)
    print(f"   >> Zonas detectadas en 1H: {len(zonas)}")
    
    if zonas:
        z = zonas[0]
        print(f"   ✅ Zona Detectada: {z['type']} (Min: {z['bottom']} - Max: {z['top']})")
    else:
        print("   ❌ ERROR: No se detectó la zona sintética.")
        return

    # 2. CREAMOS UN ESCENARIO DE 5 MINUTOS (PERFECTO)
    # El precio regresa a la zona (90-100) y hace un rechazo
    print("\n2. Generando Gatillo Micro (5m)...")
    datos_5m = [
        # Velas bajando hacia la zona
        {'timestamp': 4100, 'open': 104, 'high': 104, 'low': 102, 'close': 102, 'rsi': 45, 'volume': 100},
        {'timestamp': 4200, 'open': 102, 'high': 102, 'low': 98,  'close': 98,  'rsi': 40, 'volume': 100},
        
        # VELA GATILLO (Hammer perfecto en la zona)
        # Mecha inferior larga: (97 - 92) = 5. Total (98 - 92) = 6. Ratio > 80%
        {'timestamp': 4300, 'open': 98, 'high': 98, 'low': 92, 'close': 97, 'rsi': 35, 'volume': 500},
        
        # Vela actual (en formación)
        {'timestamp': 4400, 'open': 97, 'high': 98, 'low': 97, 'close': 97.5, 'rsi': 38, 'volume': 100}
    ]
    df_5m = pd.DataFrame(datos_5m)

    # 3. EJECUTAMOS EL CEREBRO
    print("\n3. Ejecutando Brain.analizar_mercado()...")
    cache = {'1h': df_1h, '5m': df_5m}
    
    senal = brain.analizar_mercado(cache)
    
    if senal:
        print(f"✅ ¡ÉXITO TOTAL! Señal Generada: {senal['side']} @ {senal['price']}")
        print("   Conclusión: El sistema funciona. Si no opera en real es por falta de oportunidades claras.")
    else:
        print("❌ FALLO: El cerebro no disparó.")

if __name__ == "__main__":
    correr_prueba_concepto()