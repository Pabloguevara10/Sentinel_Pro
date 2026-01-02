# =============================================================================
# UBICACIÓN: simulation/data_loader.py
# DESCRIPCIÓN: CARGADOR DE DATOS V9 (HÍBRIDO: OHLC minúscula / IND Mayúscula)
# =============================================================================

import os
import pandas as pd

def cargar_y_procesar_data():
    """
    Carga CSVs históricos.
    ESTÁNDAR CRÍTICO:
    - Precios (open, high, low, close, volume) -> MINÚSCULAS (Brain lo requiere)
    - Indicadores (RSI, ADX, MACD) -> MAYÚSCULAS (Backtest Runner lo requiere)
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data", "historical")
    
    print(f"📂 Buscando datos en: {data_dir}")

    if not os.path.exists(data_dir):
        print(f"❌ Error Crítico: La carpeta {data_dir} no existe.")
        return None

    symbol = "AAVEUSDT" 
    
    files_map = {
        f"{symbol}_1m.csv": "1m",
        f"{symbol}_5m.csv": "5m",
        f"{symbol}_15m.csv": "15m",
        # Agrega más si tienes los archivos (ej: 1h, 4h)
    }

    cache = {}
    
    for filename, tf_key in files_map.items():
        file_path = os.path.join(data_dir, filename)
        
        if not os.path.exists(file_path):
            print(f"⚠️ Aviso: No se encontró {filename}. Saltando {tf_key}.")
            continue
            
        print(f"   ⚡ Cargando {tf_key}: {filename} ...")
        
        try:
            df = pd.read_csv(file_path)
            
            # 1. Normalizar todo a minúsculas primero y quitar espacios
            df.columns = [c.strip().lower() for c in df.columns]
            
            # 2. Renombrar SOLO los Indicadores a Mayúsculas
            # (Dejamos open, high, low, close, volume en minúsculas)
            rename_map = {
                'rsi': 'RSI', 
                'adx': 'ADX',
                'macd': 'MACD', 
                'macd_hist': 'MACD_HIST', 
                'atr': 'ATR',
                'bb_upper': 'BBU', 
                'bb_lower': 'BBL', 
                'bb_mid': 'BBM'
            }
            df.rename(columns=rename_map, inplace=True)
            
            # 3. Configurar Índice
            if 'timestamp' in df.columns:
                # Detección automática de ms o segundos
                if df['timestamp'].iloc[0] > 10000000000: # Es ms
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                df.set_index('timestamp', inplace=True)
            elif 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)

            df.sort_index(inplace=True)
            cache[tf_key] = df
            
        except Exception as e:
            print(f"❌ Error leyendo {filename}: {e}")

    if '1m' not in cache:
        print("❌ Error Fatal: Falta data de 1 minuto.")
        return None
        
    print(f"✅ Carga completa. Temporalidades listas: {list(cache.keys())}")
    return cache