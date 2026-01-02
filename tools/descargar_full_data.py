# =============================================================================
# UBICACIÓN: tools/descargar_full_data.py
# DESCRIPCIÓN: MINERO DE DATOS PROFUNDO (COMPATIBLE CON DATASEEDER V18)
# =============================================================================

import time
import pandas as pd
import os
import sys
from datetime import datetime, timedelta
from binance.client import Client

# Aseguramos que Python encuentre tus módulos
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.config import Config
from tools.data_seeder import DataSeeder

class HistoricalMiner:
    def __init__(self):
        print("🔧 Inicializando Minero Histórico...")
        self.client = Client(Config.API_KEY, Config.API_SECRET)
        self.seeder = DataSeeder() # Instanciamos el motor offline V18
        self.symbol = Config.SYMBOL
        self.data_dir = Config.DIR_DATA
        
        # Un año en milisegundos (aprox)
        self.one_year_ms = 365 * 24 * 60 * 60 * 1000
        
    def ejecutar_mineria(self):
        print(f"\n🌍 INICIANDO DESCARGA TOTAL (1 AÑO) PARA: {self.symbol}")
        print("="*60)
        
        # 1. DESCARGA MAESTRA 1M (Internet)
        df_1m = self._descargar_bucle_seguro()
        
        if df_1m is None or df_1m.empty:
            print("❌ Fallo en la descarga. Abortando.")
            return

        print(f"\n💾 Guardando Maestro 1m ({len(df_1m)} velas)...")
        self._guardar_maestro(df_1m)
        
        # 2. GENERACIÓN DE DERIVADOS (Offline)
        print("\n⚙️ ACTIVANDO MOTOR DE GENERACIÓN (DataSeeder)...")
        print("   (Esto procesará 2m, 3m, 5m, 15m, 30m, 1h, 4h, 1d localmente)")
        
        # CRÍTICO: Usamos la interfaz pública del Seeder, no métodos internos.
        # El Seeder leerá el archivo 1m que acabamos de guardar.
        self.seeder.sembrar_datos()
        
        print("\n✅ PROCESO COMPLETADO EXITOSAMENTE.")
        print(f"📂 Verifica tu carpeta: {self.data_dir}")

    def _descargar_bucle_seguro(self):
        """Bucle robusto para descargar data histórica sin romper límites."""
        end_ts = int(time.time() * 1000)
        start_ts = end_ts - self.one_year_ms
        
        current_start = start_ts
        all_candles = []
        
        print(f"📅 Rango: {datetime.fromtimestamp(start_ts/1000)} -> {datetime.fromtimestamp(end_ts/1000)}")
        
        while current_start < end_ts:
            try:
                # Descarga por lotes de 1000 (Límite seguro de Binance)
                klines = self.client.get_klines(
                    symbol=self.symbol,
                    interval=Client.KLINE_INTERVAL_1MINUTE,
                    startTime=current_start,
                    limit=1000
                )
                
                if not klines:
                    break
                    
                # Procesar lote
                for k in klines:
                    all_candles.append({
                        'timestamp': int(k[0]),
                        'open': float(k[1]), 'high': float(k[2]),
                        'low': float(k[3]), 'close': float(k[4]),
                        'volume': float(k[5])
                    })
                
                # Actualizar cursor de tiempo (último cierre + 1ms)
                last_ts = int(klines[-1][0])
                current_start = last_ts + 1 
                
                # Feedback visual
                progreso = (current_start - start_ts) / (end_ts - start_ts) * 100
                if progreso > 100: progreso = 100
                fecha_actual = datetime.fromtimestamp(last_ts/1000).strftime('%Y-%m-%d %H:%M')
                
                # Imprimir sobre la misma línea para no ensuciar consola
                print(f"   [{progreso:.1f}%] {fecha_actual} | Acumulado: {len(all_candles)} velas", end='\r')
                
                # Pausa técnica para evitar Ban de IP
                time.sleep(0.1) 
                
            except Exception as e:
                print(f"\n   ❌ Error en API: {e}. Reintentando en 5s...")
                time.sleep(5)
        
        print() # Salto de línea al final
        
        if not all_candles:
            return None
            
        # Limpieza final
        df = pd.DataFrame(all_candles)
        df.drop_duplicates(subset='timestamp', inplace=True)
        df.sort_values('timestamp', inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        return df

    def _guardar_maestro(self, df):
        path = os.path.join(self.data_dir, f"{self.symbol}_1m.csv")
        # Asegurar directorio
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        df.to_csv(path, index=False)
        print(f"✅ Archivo Maestro guardado en: {path}")

if __name__ == "__main__":
    try:
        miner = HistoricalMiner()
        miner.ejecutar_mineria()
    except KeyboardInterrupt:
        print("\n🛑 Proceso interrumpido por el usuario.")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")