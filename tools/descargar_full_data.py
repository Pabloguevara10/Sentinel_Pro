import time
import pandas as pd
import os
import sys
from datetime import datetime, timedelta
from binance.client import Client

# --- IMPORTACIONES DEL ECOSISTEMA ---
# Aseguramos que Python encuentre tus módulos
sys.path.append(os.getcwd())

from config.config import Config
from tools.data_seeder import DataSeeder

class HistoricalMiner:
    def __init__(self):
        print("🔧 Inicializando Minero Histórico...")
        self.client = Client(Config.API_KEY, Config.API_SECRET)
        self.seeder = DataSeeder() # Usaremos sus herramientas de cálculo
        self.symbol = Config.SYMBOL
        self.data_dir = Config.DIR_DATA
        
        # Un año en milisegundos
        self.one_year_ms = 365 * 24 * 60 * 60 * 1000
        
    def ejecutar_mineria(self):
        print(f"\n🌍 INICIANDO DESCARGA TOTAL (1 AÑO) PARA: {self.symbol}")
        print("="*60)
        
        # 1. DESCARGA MAESTRA 1M
        df_1m = self._descargar_bucle_seguro()
        
        if df_1m is None or df_1m.empty:
            print("❌ Fallo en la descarga. Abortando.")
            return

        print(f"\n💾 Guardando Maestro 1m ({len(df_1m)} velas)...")
        # Guardamos manualmente para evitar el recorte del DataSeeder original
        path_1m = os.path.join(self.data_dir, f"{self.symbol}_1m.csv")
        
        # Procesamos indicadores base para el 1m antes de guardar
        # (Usamos el método interno del seeder para consistencia)
        self.seeder._procesar_y_guardar(df_1m, '1m')
        print(f"✅ Archivo Maestro guardado en: {path_1m}")
        
        # 2. GENERACIÓN DE CASCADA (Resampling)
        print("\n⚙️ GENERANDO TEMPORALIDADES DERIVADAS...")
        target_tfs = [tf for tf in Config.TIMEFRAMES if tf != '1m']
        
        for tf in target_tfs:
            print(f"   ↳ Procesando {tf}...", end=" ")
            try:
                # Usamos la lógica de resampling del seeder
                df_resampled = self.seeder._resamplear_df(df_1m, tf)
                
                # Calculamos indicadores y mapas FVG
                self.seeder._procesar_y_guardar(df_resampled, tf)
                print(f"✅ OK ({len(df_resampled)} velas)")
                
            except Exception as e:
                print(f"❌ ERROR: {e}")

        print("\n" + "="*60)
        print("🏁 PROCESO COMPLETADO EXITOSAMENTE")
        print("Ahora puedes ejecutar el Stress Test con data real de 1 año.")

    def _descargar_bucle_seguro(self):
        """
        Bucle de descarga paginada (1000 velas) con sleep de seguridad.
        """
        end_ts = int(time.time() * 1000)
        start_ts = end_ts - self.one_year_ms
        
        current_start = start_ts
        all_candles = []
        
        print(f"📅 Rango: {datetime.fromtimestamp(start_ts/1000)} -> {datetime.fromtimestamp(end_ts/1000)}")
        print("⏳ Descargando paquetes de 1000 velas...")

        while current_start < end_ts:
            try:
                # Descarga batch de 1000
                klines = self.client.get_klines(
                    symbol=self.symbol,
                    interval=Client.KLINE_INTERVAL_1MINUTE,
                    startTime=current_start,
                    limit=1000
                )
                
                if not klines:
                    print("   ⚠️ No hay más datos disponibles.")
                    break
                
                # Procesar batch
                for k in klines:
                    all_candles.append({
                        'timestamp': int(k[0]),
                        'open': float(k[1]),
                        'high': float(k[2]),
                        'low': float(k[3]),
                        'close': float(k[4]),
                        'volume': float(k[5])
                    })
                
                # Actualizar cursor de tiempo (último cierre + 1ms)
                last_ts = int(klines[-1][0])
                current_start = last_ts + 1 # Evitar duplicados exactos, la api usa startTime inclusivo
                
                # Feedback visual
                progreso = (current_start - start_ts) / (end_ts - start_ts) * 100
                fecha_actual = datetime.fromtimestamp(last_ts/1000).strftime('%Y-%m-%d %H:%M')
                print(f"   [{progreso:.1f}%] {fecha_actual} | Acumulado: {len(all_candles)} velas")
                
                # PAUSA ANTI-BANEO (Importante)
                time.sleep(1.0) 
                
            except Exception as e:
                print(f"   ❌ Error en API: {e}. Reintentando en 5s...")
                time.sleep(5)
        
        if not all_candles:
            return None
            
        # Convertir a DataFrame y limpiar duplicados por si acaso
        df = pd.DataFrame(all_candles)
        df.drop_duplicates(subset='timestamp', inplace=True)
        df.sort_values('timestamp', inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        return df

if __name__ == "__main__":
    try:
        miner = HistoricalMiner()
        miner.ejecutar_mineria()
    except KeyboardInterrupt:
        print("\n🛑 Proceso detenido por el usuario.")
    except Exception as e:
        print(f"\n❌ Error Fatal: {e}")