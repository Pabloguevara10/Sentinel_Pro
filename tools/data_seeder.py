# =============================================================================
# UBICACIÓN: tools/data_seeder.py
# DESCRIPCIÓN: DATA ENGINE V18.0 (OFFLINE & FAST PROCESSING)
# =============================================================================

import pandas as pd
import os
import time
from config.config import Config
from tools.precision_lab import PrecisionLab
from tools.fvg_scanner import FVGScanner

class DataSeeder:
    """
    DATA ENGINE V18.0 (MODO OFFLINE):
    - NO descarga nada de internet (eso lo hace HistoricalManager).
    - Solo procesa datos LOCALES para generar temporalidades.
    - Velocidad optimizada: Calcula indicadores en memoria RAM.
    """
    def __init__(self, api_manager=None):
        # NOTA: Ya no usamos api_manager ni client aquí. Es puramente matemático.
        self.lab = PrecisionLab()
        self.scanner = FVGScanner()
        self.symbol = Config.SYMBOL
        self.data_dir = Config.DIR_DATA
        self.maps_dir = Config.DIR_MAPS
        
    def sembrar_datos(self):
        """
        Toma el archivo MAESTRO (1m) local y fabrica los derivados.
        No consume API.
        """
        # 1. Leer MAESTRO Local (AAVEUSDT_1m.csv)
        df_1m = self._leer_maestro_local()
        
        if df_1m is None or df_1m.empty:
            print("⚠️ [SEEDER] No hay datos base 1m para procesar.")
            return

        # 2. Generar derivados (Procesamiento CPU puro)
        # Lista de objetivos (excluyendo 1m que es la fuente)
        target_tfs = ['2m', '3m', '5m', '15m', '30m', '1h', '4h', '1d']
        
        start_time = time.time()
        count = 0
        
        for tf in target_tfs:
            try:
                # A. Resampleo Matemático (Super rápido)
                df_tf = self._resamplear_dataframe(df_1m, tf)
                
                if not df_tf.empty:
                    # B. Cálculo de Indicadores y Guardado
                    self._procesar_y_guardar(df_tf, tf)
                    count += 1
            except Exception as e:
                print(f"❌ [SEEDER] Error generando {tf}: {e}")

        # Feedback de rendimiento
        elapsed = time.time() - start_time
        # Solo imprimimos si tomó tiempo perceptible (para no spammear el log)
        if elapsed > 1.0:
            print(f"⚡ [SEEDER] Motor Offline: {count} temporalidades generadas en {elapsed:.2f}s")

    def _leer_maestro_local(self):
        """Lee el archivo 1m directamente del disco SSD/HDD."""
        path = os.path.join(self.data_dir, f"{self.symbol}_1m.csv")
        if not os.path.exists(path):
            return None
        
        try:
            df = pd.read_csv(path)
            # Asegurar índice datetime
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('datetime', inplace=True)
            return df
        except Exception:
            return None

    def _resamplear_dataframe(self, df_1m, target_tf):
        """Convierte 1m -> TF Objetivo usando matemáticas de Pandas."""
        if df_1m.empty: return pd.DataFrame()
        
        # Mapeo exacto
        rule_map = {
            '2m': '2min', '3m': '3min', '5m': '5min',
            '15m': '15min', '30m': '30min',
            '1h': '1h', '4h': '4h', '1d': '1D'
        }
        
        rule = rule_map.get(target_tf)
        if not rule: return pd.DataFrame()
        
        ohlc_dict = {
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last',
            'volume': 'sum', 'timestamp': 'first'
        }
        
        try:
            # El resampleo de pandas es extremadamente eficiente
            df_res = df_1m.resample(rule).agg(ohlc_dict)
            df_res.dropna(inplace=True)
            return df_res.reset_index(drop=True)
        except Exception:
            return pd.DataFrame()

    def _procesar_y_guardar(self, df, tf):
        """
        Calcula indicadores frescos y sobreescribe el archivo derivado.
        NOTA: Sobreescribir es más seguro y rápido que 'append' para indicadores 
        como EMA/RSI que dependen de la historia previa.
        """
        # 1. Calculadora (Incluye ADX, ATR, RSI, BB...)
        df = self.lab.calcular_indicadores_full(df)
        
        # 2. Guardar CSV Derivado
        filename = f"{self.symbol}_{tf}.csv"
        path = os.path.join(self.data_dir, filename)
        
        # Limpieza de columnas duplicadas o índices
        cols_base = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        # Agregar dinámicamente las columnas de indicadores generadas por el Lab
        cols_extra = [c for c in df.columns if c not in cols_base and c != 'datetime']
        cols_final = cols_base + cols_extra
        
        df[cols_final].to_csv(path, index=False)
        
        # 3. Generar Mapa FVG (Opcional, si tu estrategia lo usa)
        self.scanner.escanear_y_guardar(df, tf, self.maps_dir)