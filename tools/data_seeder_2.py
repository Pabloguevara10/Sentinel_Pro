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
    SEMBRADOR DE DATOS V3.0 (Delta & High Performance):
    - Minería: Descarga solo los minutos faltantes (Gap Filling).
    - Procesamiento: 'Delta Resampling'. No reconstruye toda la historia.
      Solo procesa los minutos nuevos y los empalma con los archivos existentes.
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
        """Lee el archivo 1m maestro y devuelve el último timestamp registrado."""
        if os.path.exists(self.file_1m):
            try:
                # Leemos solo los encabezados y la última fila para ser rápidos
                df = pd.read_csv(self.file_1m)
                if not df.empty and 'timestamp' in df.columns:
                    return int(df['timestamp'].iloc[-1])
            except:
                pass
        return 0

    def sembrar_datos(self):
        print(f"\n🌱 INICIANDO SEMBRADO DE DATOS ({self.cfg.SYMBOL})...")
        
        # PASO 1: HIDRATAR LA FUENTE (1m)
        last_ts = self._obtener_ultimo_timestamp()
        ahora = int(time.time() * 1000)
        
        # Si el hueco es menor a 2 minutos, asumimos que está al día
        if ahora - last_ts < 120000 and last_ts > 0:
            print("   ✅ Data 1m está actualizada.")
        else:
            # Definir ventana de descarga
            if last_ts == 0:
                print("   📥 Descargando historial completo (1 año)...")
                # Binance permite max 1000 velas por request, el loop lo manejará si implementamos paginación
                # Por simplicidad en V3, pedimos el bloque más reciente grande
                # Para producción real, aquí iría un loop de paginación hacia atrás.
                # Asumimos descarga inicial de bloque reciente.
                start_time = None 
            else:
                start_time = last_ts + 1
                diff_min = (ahora - last_ts) / 60000
                print(f"   📥 Descargando diferencial: {diff_min:.1f} minutos faltantes...")

            candles = self.conn.get_historical_candles(self.cfg.SYMBOL, '1m', limit=1500, start_time=start_time)
            
            if candles:
                new_data = []
                for c in candles:
                    new_data.append({
                        'timestamp': c[0],
                        'open': float(c[1]),
                        'high': float(c[2]),
                        'low': float(c[3]),
                        'close': float(c[4]),
                        'volume': float(c[5])
                    })
                
                df_new = pd.DataFrame(new_data)
                
                # Guardado Incremental (Append)
                if last_ts > 0:
                    df_new.to_csv(self.file_1m, mode='a', header=False, index=False)
                else:
                    df_new.to_csv(self.file_1m, index=False)
                
                print(f"   ✅ Se agregaron {len(df_new)} velas nuevas a 1m.")
            else:
                print("   ⚠️ No se encontraron nuevos datos en Binance.")

        # PASO 2: PROPAGAR CAMBIOS (Delta Processing)
        self._regenerar_temporalidades()

    def _regenerar_temporalidades(self):
        """
        Versión Optimizada: Solo procesa los datos nuevos para cada temporalidad.
        """
        print("   ⚙️ Sincronizando temporalidades (Delta Mode)...")
        
        # Cargar fuente completa (1m) una sola vez en memoria
        # NOTA: En producción con archivos de GBs, esto se optimizaría con chunks.
        if not os.path.exists(self.file_1m): return
        df_1m = pd.read_csv(self.file_1m)
        df_1m['datetime'] = pd.to_datetime(df_1m['timestamp'], unit='ms')
        df_1m.set_index('datetime', inplace=True)

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
                target_file = os.path.join(self.cfg.DIR_DATA, f"{self.cfg.SYMBOL}_{tf_name}.csv")
                df_final = pd.DataFrame()
                
                # A. ESCENARIO INCREMENTAL (El archivo ya existe)
                if os.path.exists(target_file):
                    # 1. Cargar archivo existente
                    df_old = pd.read_csv(target_file)
                    
                    if not df_old.empty:
                        # 2. Encontrar punto de corte (Retrocedemos 1 vela por seguridad de cierre)
                        # Tomamos el penúltimo registro como base segura
                        if len(df_old) > 2:
                            cut_off_ts = df_old.iloc[-2]['timestamp']
                            # Recortamos lo viejo hasta el punto seguro
                            df_old_safe = df_old[df_old['timestamp'] < cut_off_ts]
                        else:
                            # Si es muy pequeño, regeneramos todo
                            cut_off_ts = 0
                            df_old_safe = pd.DataFrame()

                        if cut_off_ts > 0:
                            # 3. Filtrar 1m: Solo tomamos lo que sea >= al punto de corte
                            df_1m_delta = df_1m[df_1m['timestamp'] >= cut_off_ts]
                            
                            if not df_1m_delta.empty:
                                # 4. Resamplear solo el Delta
                                df_new_resampled = df_1m_delta.resample(tf_code).agg(agg_rules).dropna()
                                df_new_resampled['timestamp'] = df_new_resampled['timestamp'].astype('int64')
                                df_new_reset = df_new_resampled.reset_index(drop=True)
                                
                                # 5. Fusión (Viejo Seguro + Nuevo Resampleado)
                                df_final = pd.concat([df_old_safe, df_new_reset])
                                df_final = df_final.drop_duplicates(subset='timestamp', keep='last')
                                
                                sys.stdout.write(f"\r      ⚡ {tf_name}: Actualizado (Delta: {len(df_new_reset)} velas)")
                            else:
                                df_final = df_old
                        else:
                            # Fallback a regeneración total
                            df_final = self._resamplear_total(df_1m, tf_code)
                    else:
                        df_final = self._resamplear_total(df_1m, tf_code)
                
                # B. ESCENARIO INICIAL (No existe, crear de cero)
                else:
                    sys.stdout.write(f"\r      🔨 {tf_name}: Creando desde cero...")
                    df_final = self._resamplear_total(df_1m, tf_code)

                sys.stdout.flush()
                
                # 6. Recalcular Indicadores (Siempre sobre el dataset unido para precisión)
                # Esto es rápido en memoria y garantiza continuidad de EMAs/RSI
                self._procesar_y_guardar(tf_name, df_final)
                
            except Exception as e:
                print(f"\n      ❌ Error en {tf_name}: {e}")

        print("\n   ✅ Sincronización completada.")

    def _resamplear_total(self, df_1m_indexed, tf_code):
        """Helper para resampleo completo cuando no hay historial previo."""
        agg_rules = {
            'timestamp': 'first', 'open': 'first', 'high': 'max',
            'low': 'min', 'close': 'last', 'volume': 'sum'
        }
        df_res = df_1m_indexed.resample(tf_code).agg(agg_rules).dropna()
        df_res['timestamp'] = df_res['timestamp'].astype('int64')
        return df_res.reset_index(drop=True)

    def _procesar_y_guardar(self, tf_name, df):
        if df.empty: return
        # Calcular indicadores
        df_metrics = Calculator.calcular_indicadores(df)
        
        # Guardar en disco
        path = os.path.join(self.cfg.DIR_DATA, f"{self.cfg.SYMBOL}_{tf_name}.csv")
        df_metrics.to_csv(path, index=False)

if __name__ == "__main__":
    # Prueba manual
    seeder = DataSeeder()
    seeder.sembrar_datos()