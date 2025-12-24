<<<<<<< HEAD
=======
# =============================================================================
# UBICACIÓN: tools/data_seeder.py
# DESCRIPCIÓN: DATA ENGINE 2.0 (SAFE GAP FILLING + NON-BLOCKING PERSISTENCE)
# =============================================================================

>>>>>>> 4c4d97b (commit 24/12)
import time
import pandas as pd
import os
from binance.client import Client
from config.config import Config
from tools.precision_lab import PrecisionLab
from tools.fvg_scanner import FVGScanner

class DataSeeder:
<<<<<<< HEAD
    """
    DATA ENGINE 2.0 (Resampling Core):
    1. Descarga/Sincroniza SOLO velas de 1m.
    2. Resamplea matemáticamente para generar 3m, 5m, 15m, 30m, 1h, 4h, 1d.
    3. Calcula indicadores (incluyendo ADX/ATR) y actualiza mapas FVG.
    """
    def __init__(self):
        self.client = Client(Config.API_KEY, Config.API_SECRET, testnet=Config.TESTNET)
        self.lab = PrecisionLab()
        self.scanner = FVGScanner()
        self.symbol = Config.SYMBOL
        self.data_dir = Config.DIR_DATA
        self.maps_dir = Config.DIR_MAPS
        
    def sembrar_datos(self):
        """Método principal llamado por el Bot."""
        # 1. Sincronizar la base atómica (1m)
        df_1m = self._sincronizar_base_1m()
        
        if df_1m is None or df_1m.empty:
            print("⚠️ Error crítico: No hay datos 1m base.")
            return

        # 2. Generar temporalidades superiores (Resampling)
        # Lista de TFs a generar (excluyendo 1m que ya tenemos)
        target_tfs = [tf for tf in Config.TIMEFRAMES if tf != '1m']
        
        # Procesamos primero el 1m para indicadores y FVG
        self._procesar_y_guardar(df_1m, '1m')
        
        for tf in target_tfs:
            try:
                # Resampleo
                df_resampled = self._resamplear_df(df_1m, tf)
                # Cálculo de Indicadores + Guardado + FVG
                self._procesar_y_guardar(df_resampled, tf)
            except Exception as e:
                print(f"❌ Error generando {tf}: {e}")

    def _sincronizar_base_1m(self):
        """Descarga o actualiza el archivo maestro de 1m."""
        path_1m = os.path.join(self.data_dir, f"{self.symbol}_1m.csv")
        
        # A. Determinar fecha de inicio
        start_str = "1 month ago UTC" # Default para arranque en limpio
        
        if os.path.exists(path_1m):
            try:
                # Leer solo la última fila para ver el timestamp
                df_existente = pd.read_csv(path_1m)
                if not df_existente.empty:
                    last_ts = df_existente.iloc[-1]['timestamp']
                    # Convertir ms a string fecha para Binance
                    start_str = str(int(last_ts) + 60000) # +1 minuto
            except:
                pass # Si falla lectura, bajamos todo de nuevo

        # B. Descargar Delta
        try:
            klines = self.client.get_historical_klines(
                self.symbol, 
                Client.KLINE_INTERVAL_1MINUTE, 
                start_str
            )
        except Exception as e:
            print(f"⚠️ Error API Binance: {e}")
            return self._cargar_csv_seguro(path_1m)

        if not klines:
            return self._cargar_csv_seguro(path_1m)

        # C. Procesar nuevos datos
        new_data = []
        for k in klines:
            new_data.append({
                'timestamp': int(k[0]),
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            })
        
        df_new = pd.DataFrame(new_data)
        
        # D. Fusionar y Guardar
        if os.path.exists(path_1m):
            df_old = pd.read_csv(path_1m)
            df_final = pd.concat([df_old, df_new]).drop_duplicates(subset='timestamp', keep='last')
        else:
            df_final = df_new
            
        # Recortar exceso histórico (mantenemos un buffer saludable)
        limit = Config.LIMIT_CANDLES * 5 # Guardamos más 1m para poder armar velas grandes
        if len(df_final) > limit:
            df_final = df_final.iloc[-limit:]
            
        return df_final.reset_index(drop=True)

    def _resamplear_df(self, df_1m, target_tf):
        """Convierte velas de 1m a Target TF (ej. 15m) usando Pandas Resample."""
        # Convertir timestamp a datetime index para resampling
        df = df_1m.copy()
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('datetime', inplace=True)
        
        # Mapeo de reglas pandas (1m -> 1T, 1h -> 1H)
        rule_map = {
            '3m': '3min', '5m': '5min', '15m': '15min', 
            '30m': '30min', '1h': '1H', '4h': '4H', '1d': '1D'
        }
        rule = rule_map.get(target_tf, '1H')
        
        # Lógica de agregación (OHLCV)
        ohlc_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'timestamp': 'first' # Mantenemos el timestamp de apertura
        }
        
        df_res = df.resample(rule).agg(ohlc_dict)
        df_res.dropna(inplace=True) # Eliminar velas incompletas/vacías
        return df_res.reset_index(drop=True)

    def _procesar_y_guardar(self, df, tf):
        """Calcula indicadores y guarda CSVs + Mapas FVG."""
        # 1. Calculadora (Incluye ADX, ATR, RSI...)
        df_calc = self.lab.calcular_indicadores_full(df)
        
        # 2. Guardar Data Histórica
=======
    def __init__(self, api_manager=None):
        """
        Inicializa el motor de datos con soporte para inyección de dependencias.
        """
        self.using_connector = False
        if api_manager and hasattr(api_manager, 'client'):
            self.client = api_manager.client
            self.using_connector = True
        else:
            self.client = Client(Config.API_KEY, Config.API_SECRET, testnet=Config.TESTNET)
            self.using_connector = False
            
        self.lab = PrecisionLab()
        self.scanner = FVGScanner()
        self.symbol = Config.SYMBOL
        self.data_dir = Config.DIR_DATA
        self.maps_dir = Config.DIR_MAPS
        
    def sembrar_datos(self):
        """
        Método Maestro:
        1. Sincroniza 1m (Protocolo de Estabilidad).
        2. Resamplea a temporalidades superiores.
        3. Calcula indicadores y mapas FVG.
        """
        print(f"🚜 Sembrando datos para {self.symbol}...")
        
        # 1. Sincronizar Base 1m (Lógica Blindada)
        df_1m = self._sincronizar_base_1m()
        
        if df_1m is None or df_1m.empty:
            print("⚠️ Error crítico: No hay datos 1m base. Saltando ciclo de análisis.")
            return

        # 2. Generar temporalidades superiores (Resampling)
        # Procesamos primero el 1m para indicadores y FVG
        self._procesar_y_guardar(df_1m, '1m')
        
        target_tfs = [tf for tf in Config.TIMEFRAMES if tf != '1m']
        
        for tf in target_tfs:
            try:
                df_resampled = self._resamplear_df(df_1m, tf)
                if not df_resampled.empty:
                    self._procesar_y_guardar(df_resampled, tf)
            except Exception as e:
                print(f"❌ Error generando {tf}: {e}")
        
        # print("✅ Ciclo de datos completado.") # Ruido reducido

    def _sincronizar_base_1m(self):
        """
        Sincronización Inteligente V3:
        - Gap Fill desde penúltima línea.
        - Persistencia Limitada (Max 2 intentos).
        - Nunca borra data existente por error de red.
        """
        path = os.path.join(self.data_dir, f"{self.symbol}_1m.csv")
        
        # --- 1. CONFIGURACIÓN DE INICIO ---
        start_ts = int((time.time() - 365*24*60*60) * 1000) # 1 año atrás default
        mode = 'w'
        header = True
        
        # --- 2. VALIDACIÓN NO DESTRUCTIVA ---
        if os.path.exists(path):
            try:
                # Leemos para verificar integridad y encontrar punto de empalme
                df_check = pd.read_csv(path) 
                
                if not df_check.empty and 'timestamp' in df_check.columns:
                    # LÓGICA DE EMPALME SEGURO (Penúltima línea)
                    if len(df_check) > 2:
                        last_ts = int(df_check.iloc[-2]['timestamp']) # Penúltima
                    else:
                        last_ts = int(df_check.iloc[-1]['timestamp']) # Última
                    
                    start_ts = last_ts 
                    mode = 'a' # APPEND (Nunca borrar)
                    header = False
                    # print(f"📂 Archivo verificado. Sincronizando desde: {pd.to_datetime(start_ts, unit='ms')}")
                else:
                    print("⚠️ Archivo existente vacío. Se regenerará.")
                    
            except pd.errors.ParserError:
                print(f"⚠️ ARCHIVO CORRUPTO DETECTADO. Regenerando historial...")
                mode = 'w'; header = True
            except Exception as e:
                print(f"⚠️ Error de acceso al archivo ({e}). Se usará data existente sin actualizar.")
                return pd.read_csv(path) if os.path.exists(path) else None

        # --- 3. BUCLE DE DESCARGA (Persistencia No Bloqueante) ---
        now = int(time.time() * 1000)
        current_ts = start_ts
        intentos_fallidos = 0
        MAX_INTENTOS = 2
        
        # Si estamos al día (menos de 2 mins), retornamos rápido
        if (now - start_ts) < 120000:
            if os.path.exists(path): return pd.read_csv(path)
        
        while current_ts < now:
            try:
                # Selección de método API correcto
                if self.using_connector:
                    candles = self.client.klines(symbol=self.symbol, interval="1m", limit=1000, startTime=current_ts)
                else:
                    candles = self.client.futures_klines(symbol=self.symbol, interval="1m", limit=1000, startTime=current_ts)
                
                if not candles:
                    break # No hay más data en el exchange
                
                # Procesamiento
                data = []
                for c in candles:
                    data.append({
                        'timestamp': c[0],
                        'open': float(c[1]), 'high': float(c[2]), 
                        'low': float(c[3]), 'close': float(c[4]), 
                        'volume': float(c[5])
                    })
                
                df_batch = pd.DataFrame(data)
                
                # Escritura Segura (Append)
                write_mode = mode # 'a' o 'w'
                write_header = header
                
                df_batch.to_csv(path, mode=write_mode, header=write_header, index=False)
                
                # Actualizar cursor y flags
                last_candle_ts = data[-1]['timestamp']
                current_ts = last_candle_ts + 60000
                mode = 'a'; header = False 
                intentos_fallidos = 0 # Reset de contador si tenemos éxito
                
                now = int(time.time() * 1000) # Actualizar 'now' para evitar bucle infinito

            except Exception as e:
                intentos_fallidos += 1
                print(f"📡 Error de Red ({intentos_fallidos}/{MAX_INTENTOS}): {e}")
                
                if intentos_fallidos >= MAX_INTENTOS:
                    print("⚠️ Red inestable. Saltando actualización para priorizar operativa.")
                    break # SALIR DEL BUCLE Y RETORNAR DATA VIEJA
                
                time.sleep(1) # Espera breve antes de reintentar
        
        # --- 4. LIMPIEZA FINAL Y RETORNO ---
        if os.path.exists(path):
            try:
                # Cargar y limpiar duplicados generados por el empalme seguro
                df_final = pd.read_csv(path)
                df_final.drop_duplicates(subset='timestamp', keep='last', inplace=True)
                return df_final
            except Exception:
                return pd.DataFrame()
            
        return pd.DataFrame()

    def _resamplear_df(self, df_1m, target_tf):
        """Convierte velas de 1m a Target TF usando Pandas Resample."""
        if df_1m.empty: return pd.DataFrame()
        
        df = df_1m.copy()
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('datetime', inplace=True)
        
        rule_map = {
            '3m': '3min', '5m': '5min', '15m': '15min', 
            '30m': '30min', '1h': '1h', '4h': '4h', '1d': '1D'
        }
        rule = rule_map.get(target_tf)
        if not rule: return pd.DataFrame()
        
        ohlc_dict = {
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last',
            'volume': 'sum', 'timestamp': 'first'
        }
        
        try:
            df_res = df.resample(rule).agg(ohlc_dict)
            df_res.dropna(inplace=True)
            return df_res.reset_index(drop=True)
        except Exception:
            return pd.DataFrame()

    def _procesar_y_guardar(self, df, tf):
        """Calcula indicadores y guarda CSVs + Mapas FVG."""
        if df.empty: return

        # 1. Calculadora (Incluye ADX, ATR, RSI...)
        df_calc = self.lab.calcular_indicadores_full(df)
        
        # 2. Guardar Data Histórica (Derivados se sobrescriben, es rápido)
>>>>>>> 4c4d97b (commit 24/12)
        path = os.path.join(self.data_dir, f"{self.symbol}_{tf}.csv")
        df_calc.to_csv(path, index=False)
        
        # 3. Escáner FVG
<<<<<<< HEAD
        self.scanner.escanear_y_guardar(df_calc, tf, self.maps_dir)
        
    def _cargar_csv_seguro(self, path):
        if os.path.exists(path):
            return pd.read_csv(path)
        return None
=======
        self.scanner.escanear_y_guardar(df_calc, tf, self.maps_dir)
>>>>>>> 4c4d97b (commit 24/12)
