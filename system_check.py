# =============================================================================
# NOMBRE: system_check.py
# DESCRIPCIÓN: DIAGNÓSTICO PRE-VUELO SENTINEL PRO (TRIAD READY)
# =============================================================================

import os
import sys
import pandas as pd
from config.config import Config

# Ajuste de path para imports
sys.path.append(os.getcwd())

def verificar_importaciones():
    print("🔍 1. Verificando Módulos del Ecosistema...")
    try:
        from logic.brain import Brain
        from logic.shooter import Shooter
        from execution.comptroller import Comptroller
        from tools.StructureScanner_2 import StructureScanner
        print("   ✅ Lógica y Herramientas (Brain, Shooter, Scanner) encontradas.")
    except ImportError as e:
        print(f"   ❌ ERROR CRÍTICO DE IMPORTACIÓN: {e}")
        print("      Asegúrate de que 'StructureScanner_2.py' esté en la carpeta 'tools'.")
        return False
    return True

def verificar_datos():
    print("\n🔍 2. Verificando Datos Históricos (Requeridos por Tríada)...")
    base_dir = Config.DIR_DATA
    required_tfs = ['15m', '1h', '4h']
    symbol = Config.SYMBOL
    
    missing = []
    dfs = {}
    
    for tf in required_tfs:
        path = os.path.join(base_dir, f"{symbol}_{tf}.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                # Verificar columnas mínimas
                cols = ['timestamp', 'open', 'high', 'low', 'close']
                if all(c in df.columns for c in cols):
                    print(f"   ✅ {symbol}_{tf}.csv: OK ({len(df)} velas)")
                    dfs[tf] = df
                else:
                    print(f"   ⚠️ {symbol}_{tf}.csv: Columnas incompletas.")
                    missing.append(tf)
            except Exception as e:
                print(f"   ❌ Error leyendo {tf}: {e}")
                missing.append(tf)
        else:
            print(f"   ❌ FALTA ARCHIVO: {path}")
            missing.append(tf)
            
    if missing:
        print("   ⛔ NO SE PUEDE INICIAR: Faltan datos críticos.")
        return False, None
    return True, dfs

def prueba_de_fuego_brain(dfs):
    print("\n🧠 3. Prueba de Fuego del CEREBRO (Simulación de 1 Ciclo)...")
    try:
        from logic.brain import Brain
        brain = Brain(Config)
        
        # Inyectar datos cargados
        print("   ...Analizando mercado con lógica Gamma/Swing/Shadow...")
        signals = brain.analizar_mercado(dfs)
        
        print(f"   ✅ Análisis completado sin errores.")
        if signals:
            print(f"   ⚡ ¡SEÑALES DETECTADAS EN DATA HISTÓRICA! ({len(signals)})")
            for s in signals:
                print(f"      -> {s['strategy']} | {s['signal']} | Precio: {s['price']}")
        else:
            print("   💤 Ninguna señal en la última vela (Comportamiento normal).")
            
        return True
    except Exception as e:
        print(f"   ❌ EL CEREBRO COLAPSÓ: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*60)
    print(f"🛡️ DIAGNÓSTICO SENTINEL PRO: {Config.VERSION}")
    print("="*60)
    
    if not verificar_importaciones(): return
    ok_data, dfs = verificar_datos()
    if not ok_data: return
    
    if prueba_de_fuego_brain(dfs):
        print("\n" + "="*60)
        print("🚀 SISTEMA LISTO PARA EL DESPEGUE (ejecuta main.py)")
        print("="*60)
    else:
        print("\n🛑 REVISAR ERRORES ANTES DE INICIAR.")

if __name__ == "__main__":
    main()