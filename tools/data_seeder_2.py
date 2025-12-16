import pandas as pd
import os
import sys
import time
from datetime import datetime, timedelta

# Ajuste de rutas
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import Config
from connections.api_manager import APIManager
from logs.system_logger import SystemLogger
from data.calculator import Calculator

class DataSeeder:
    """
    SEMBRADOR DE DATOS V2.0 (Incremental Inteligente):
    - Si hay data: Descarga solo lo que falta (Gap Filling).
    - Si no hay data: Descarga 1 año completo.
    - Regenera todas las temporalidades y métricas.
    """
    def __init__(self):
        self.cfg = Config()
        self.log = SystemLogger()
        self.conn = APIManager(self.log)
        
        self.target_timeframes = {
            '3m': '3min', '5m': '5min', '15m': '15min',
            '30m': '30min', '1h': '1h', '4h': '4h', '1d': '1D'
        }
        
        self.file_1m = os.path.join(self.cfg.DIR_DATA, f"{self.cfg.SYMBOL}_1m.csv")

    def _obtener_ultimo_timestamp(self):
        """Lee el archivo 1m y devuelve el último timestamp registrado."""
        if not os.path.exists(self.file_1m):
            return None
            
        try:
            # Leemos solo la última fila para ser rápidos
            # O leemos todo si necesitamos concatenar después (mejor leer todo para recalcular métricas)
            print(f"   📂 Leyendo base de datos existente: {self.file_1m}")
            df = pd.read_csv(self.file_1m)
            
            if df.empty or 'timestamp' not in df.columns:
                return None
                
            last_ts = int(df['timestamp'].iloc[-1])
            return last_ts, df
        except Exception as e:
            print(f"   ⚠️ Error leyendo archivo existente: {e}")
            return None

    def actualizar_base_datos(self):
        symbol = self.cfg.SYMBOL
        interval = '1m'
        limit_per_req = 1000
        
        # 1. Definir Punto de Partida
        resultado_lectura = self._obtener_ultimo_timestamp()
        
        if resultado_lectura:
            last_ts_local, df_existente = resultado_lectura
            start_time = last_ts_local + 60000 # +1 minuto
            print(f"\n🔄 MODO INCREMENTAL: Actualizando desde {datetime.fromtimestamp(start_time/1000)}")
        else:
            df_existente = pd.DataFrame()
            # Si no hay data, bajamos 365 días
            start_time = int((datetime.now() - timedelta(days=365)).timestamp() * 1000)
            print(f"\n🚜 MODO GÉNESIS: Descargando 1 año desde cero.")

        end_time = int(time.time() * 1000)
        
        # Si la data está al día (menos de 1 min de diferencia), no hacemos nada
        if end_time - start_time < 60000:
            print("✅ La base de datos ya está actualizada.")
            # Igual regeneramos derivados por si acaso se borraron los otros archivos
            if not df_existente.empty:
                self.generar_derivados_y_guardar(df_existente)
            return

        # 2. Descarga del GAP
        all_candles = []
        current_start = start_time
        
        print(f"   📥 Solicitando datos a Binance...")
        while current_start < end_time:
            # Imprimir progreso
            readable_start = datetime.fromtimestamp(current_start/1000)
            sys.stdout.write(f"\r      Descargando lote: {readable_start}")
            sys.stdout.flush()
            
            candles = self.conn.get_historical_candles(symbol, interval, limit=limit_per_req, start_time=current_start)
            
            if not candles:
                break
                
            for c in candles:
                all_candles.append({
                    'timestamp': int(c[0]),
                    'open': float(c[1]),
                    'high': float(c[2]),
                    'low': float(c[3]),
                    'close': float(c[4]),
                    'volume': float(c[5])
                })
            
            last_ts_batch = int(candles[-1][0])
            current_start = last_ts_batch + 60000
            time.sleep(0.1) # Respeto a la API
            
            if current_start > end_time: break

        print(f"\n   ✅ Descarga finalizada. Nuevas velas: {len(all_candles)}")
        
        if not all_candles and df_existente.empty:
            print("❌ No se obtuvieron datos.")
            return

        # 3. Fusión (Merge)
        if all_candles:
            df_nuevo = pd.DataFrame(all_candles)
            if not df_existente.empty:
                # Concatenar y asegurar que no haya duplicados
                df_total = pd.concat([df_existente, df_nuevo])
                df_total.drop_duplicates(subset='timestamp', keep='last', inplace=True)
            else:
                df_total = df_nuevo
        else:
            df_total = df_existente

        # Ordenar estrictamente
        df_total.sort_values('timestamp', inplace=True)
        df_total.reset_index(drop=True, inplace=True)
        
        # 4. Generar Ecosistema Completo
        self.generar_derivados_y_guardar(df_total)

    def generar_derivados_y_guardar(self, df_1m):
        """Toma la data 1m completa (vieja + nueva) y regenera todo."""
        
        # Limpiar columnas de métricas viejas para recalcular limpio
        cols_base = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        df_clean = df_1m[cols_base].copy()
        
        print("\n⚙️ Recalculando métricas y generando temporalidades...")
        
        # 1. Guardar Maestro 1m
        self._procesar_y_guardar('1m', df_clean)
        
        # Preparar resampling
        df_resample = df_clean.copy()
        df_resample['datetime'] = pd.to_datetime(df_resample['timestamp'], unit='ms')
        df_resample.set_index('datetime', inplace=True)
        
        agg_rules = {
            'timestamp': 'first',
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        
        for tf_name, tf_code in self.target_timeframes.items():
            try:
                sys.stdout.write(f"\r   🔨 Construyendo {tf_name}...")
                sys.stdout.flush()
                
                df_new = df_resample.resample(tf_code).agg(agg_rules).dropna()
                df_new['timestamp'] = df_new['timestamp'].astype('int64')
                df_final = df_new.reset_index(drop=True)
                
                self._procesar_y_guardar(tf_name, df_final)
            except Exception as e:
                print(f" Error en {tf_name}: {e}")

        print("\n\n✅ ¡ACTUALIZACIÓN COMPLETADA! El sistema está listo.")

    def _procesar_y_guardar(self, tf_name, df):
        # Calcular indicadores frescos sobre toda la serie
        df_metrics = Calculator.calcular_indicadores(df.copy())
        filename = f"{self.cfg.SYMBOL}_{tf_name}.csv"
        path = os.path.join(self.cfg.DIR_DATA, filename)
        df_metrics.to_csv(path, index=False)

if __name__ == "__main__":
    seeder = DataSeeder()
    seeder.actualizar_base_datos()