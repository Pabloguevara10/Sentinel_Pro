# =============================================================================
# UBICACIÓN: tools/data_seeder.py
# DESCRIPCIÓN: DATA ENGINE 2.0 (SAFE GAP FILLING + NON-BLOCKING PERSISTENCE)
# =============================================================================

import time
import pandas as pd
import os
from binance.client import Client
from config.config import Config
from tools.precision_lab import PrecisionLab
from tools.fvg_scanner import FVGScanner

class DataSeeder:
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
        path = os.path.join(self.data_dir, f"{self.symbol}_{tf}.csv")
        df_calc.to_csv(path, index=False)
        
        # 3. Escáner FVG
        self.scanner.escanear_y_guardar(df_calc, tf, self.maps_dir)