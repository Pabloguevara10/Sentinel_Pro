import pandas as pd
import os
import time
from datetime import datetime
from config.config import Config
from data.calculator import Calculator

class HistoricalDataManager:
    """
    DEPARTAMENTO DE INVESTIGACIÓN (Gestión de Archivos):
    Administra la base de datos histórica local. Sincroniza huecos (gaps)
    y asegura que el 'Cerebro' siempre tenga datos frescos.
    VERSION: 8.2 (Soporte para columna 'ts')
    """
    def __init__(self, config, api_conn, logger):
        self.cfg = config
        self.conn = api_conn
        self.log = logger
        self.cache = {} 
        
        self.timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        self.files = {tf: os.path.join(Config.DIR_DATA, f"{Config.SYMBOL}_{tf}.csv") for tf in self.timeframes}

    def inicializar_datos(self):
        self.log.registrar_actividad("DATA_MANAGER", "📂 Iniciando carga y sincronización de datos históricos...")
        
        for tf in self.timeframes:
            # 1. Cargar lo que tengamos en disco
            df = self._cargar_csv(tf)
            
            # 2. Verificar data local
            last_timestamp = 0
            if not df.empty:
                last_timestamp = int(df['timestamp'].iloc[-1])
                readable_date = datetime.fromtimestamp(last_timestamp/1000).strftime('%Y-%m-%d %H:%M')
                self.log.registrar_actividad("DATA_MANAGER", f"   >> {tf}: Data local encontrada hasta {readable_date}")
            else:
                self.log.registrar_actividad("DATA_MANAGER", f"   >> {tf}: No hay data local o nombre incorrecto. Se descargará inicial.")
            
            # 3. Minar lo que falta (Gap Filling)
            df_actualizado = self._sincronizar_gap(tf, df, last_timestamp)
            
            # 4. Enriquecer con indicadores
            self.log.registrar_actividad("DATA_MANAGER", f"   >> {tf}: Calculando indicadores técnicos...")
            df_enriquecido = Calculator.calcular_indicadores(df_actualizado)
            
            # 5. Guardar en Caché y Disco
            self.cache[tf] = df_enriquecido
            if not df_enriquecido.empty:
                self._guardar_csv(tf, df_enriquecido)
            
        self.log.registrar_actividad("DATA_MANAGER", "✅ Base de datos sincronizada y lista.")
        return self.cache

    def _sincronizar_gap(self, timeframe, df_local, last_ts):
        """Descarga velas faltantes."""
        if last_ts == 0:
            candles = self.conn.get_historical_candles(self.cfg.SYMBOL, timeframe, limit=1000)
        else:
            ahora = int(time.time() * 1000)
            if ahora - last_ts < 60000: return df_local # Está al día
            candles = self.conn.get_historical_candles(self.cfg.SYMBOL, timeframe, start_time=last_ts + 1, limit=1000)
        
        if not candles: return df_local

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
        
        if df_local.empty:
            return df_new
        else:
            df_final = pd.concat([df_local, df_new])
            df_final = df_final.drop_duplicates(subset='timestamp', keep='last')
            return df_final

    def _cargar_csv(self, timeframe):
        """Carga CSV y normaliza nombres de columnas (ts -> timestamp)."""
        path = self.files[timeframe]
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                # FIX: Normalizar nombre de columna 'ts' a 'timestamp'
                if 'ts' in df.columns and 'timestamp' not in df.columns:
                    df.rename(columns={'ts': 'timestamp'}, inplace=True)
                
                # Asegurar que tenemos las columnas base
                required = ['timestamp', 'close']
                if not all(col in df.columns for col in required):
                    return pd.DataFrame()
                    
                return df
            except Exception:
                return pd.DataFrame()
        return pd.DataFrame()

    def _guardar_csv(self, timeframe, df):
        # Guardamos siempre como 'timestamp' para estandarizar
        path = self.files[timeframe]
        df.to_csv(path, index=False)