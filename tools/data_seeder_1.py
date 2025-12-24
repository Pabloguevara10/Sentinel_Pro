import time
import pandas as pd
import os
from binance.client import Client
from config.config import Config
from tools.precision_lab import PrecisionLab
from tools.fvg_scanner import FVGScanner

class DataSeeder:
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
        path = os.path.join(self.data_dir, f"{self.symbol}_{tf}.csv")
        df_calc.to_csv(path, index=False)
        
        # 3. Escáner FVG
        self.scanner.escanear_y_guardar(df_calc, tf, self.maps_dir)
        
    def _cargar_csv_seguro(self, path):
        if os.path.exists(path):
            return pd.read_csv(path)
        return None