import pandas as pd
import os
import sys
from datetime import datetime

# Ajuste de rutas
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import Config

def auditar_archivos():
    cfg = Config()
    print("\n📊 AUDITORÍA DE ARCHIVOS HISTÓRICOS")
    print(f"   Ruta: {cfg.DIR_DATA}")
    print("-" * 60)
    
    timeframes = ['1m', '5m', '1h']
    
    for tf in timeframes:
        file = f"{cfg.SYMBOL}_{tf}.csv"
        path = os.path.join(cfg.DIR_DATA, file)
        
        if not os.path.exists(path):
            print(f"❌ {tf}: NO EXISTE ({file})")
            continue
            
        try:
            df = pd.read_csv(path)
            # Normalizar nombre
            if 'ts' in df.columns: df.rename(columns={'ts': 'timestamp'}, inplace=True)
            
            count = len(df)
            if count == 0:
                print(f"❌ {tf}: Archivo vacío.")
                continue
                
            start = datetime.fromtimestamp(df.iloc[0]['timestamp']/1000)
            end = datetime.fromtimestamp(df.iloc[-1]['timestamp']/1000)
            duration = end - start
            
            print(f"✅ {tf}: {count} velas")
            print(f"      Inicio: {start}")
            print(f"      Fin:    {end}")
            print(f"      Duración: {duration}")
            
            if tf == '5m' and count < 300:
                print("      ⚠️ ALERTA: Data insuficiente para indicadores (Min 300 req).")
                
        except Exception as e:
            print(f"❌ {tf}: Error de lectura ({e})")
            
    print("-" * 60)

if __name__ == "__main__":
    auditar_archivos()