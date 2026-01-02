# =============================================================================
# UBICACIÓN: data/historical_manager.py
# DESCRIPCIÓN: GESTOR DE DATOS HISTÓRICOS (CORREGIDO V17.9)
# =============================================================================

import pandas as pd
import os
import time
from datetime import datetime, timedelta

# --- CORRECCIÓN DE IMPORTACIONES ---
# Usamos los archivos estándar (sin _1, _2)
from config.config import Config
from data.calculator import Calculator
from tools.fvg_scanner import FVGScanner

class HistoricalManager:
    """
    GESTOR DE DATOS HISTÓRICOS (V12.5 - ESTANDARIZADO):
    - Gestiona la descarga y almacenamiento de CSVs.
    - Sincroniza velas faltantes (Gap Filling).
    - Provee datos cacheados al Brain.
    """
    def __init__(self, api_manager, logger):
        self.api = api_manager
        self.log = logger
        self.base_dir = Config.DIR_DATA
        self.fvg_scanner = FVGScanner()
        
        self.master_tf = '1m'
        self.target_tfs = ['15m', '1h', '4h'] # TFs críticos para la Tríada

    def sincronizar_infraestructura_datos(self):
        # 1. SINCRONIZACIÓN QUIRÚRGICA DEL MAESTRO (1m)
        cambios_realizados = self._sincronizar_master_1m()
        
        # Si hubo cambios o faltan derivados, procesar todo
        if cambios_realizados or not self._verificar_derivados_existen():
            self.log.registrar_actividad("DATA_MINER", "🔄 Procesando cascada de temporalidades...")
            return self._regenerar_derivados()
            
        return True

    def _regenerar_derivados(self):
        # Cargar Master Actualizado
        path_master = os.path.join(self.base_dir, f"{Config.SYMBOL}_{self.master_tf}.csv")
        try:
            df_master = pd.read_csv(path_master)
            # Asegurar datetime
            if 'timestamp' in df_master.columns:
                 df_master['datetime'] = pd.to_datetime(df_master['timestamp'], unit='ms')
                 df_master.set_index('datetime', inplace=True)
        except Exception as e:
            self.log.registrar_error("DATA_MINER", f"Error leyendo Master 1m: {e}")
            return False

        # Preparar carpeta FVG
        dir_mapas = os.path.join(self.base_dir, "mapas_fvg")
        if not os.path.exists(dir_mapas): os.makedirs(dir_mapas)

        # 2. GENERACIÓN DE DERIVADOS
        for tf in self.target_tfs:
            try:
                # Resampleo usando Calculator
                df_procesado = Calculator.resample_data(df_master, tf)

                if df_procesado is not None and not df_procesado.empty:
                    # Indicadores
                    df_final = Calculator.agregar_indicadores(df_procesado)
                    
                    # Guardar CSV Velas
                    self._guardar_csv(df_final, tf)
                    
                    # Generar FVG (Opcional, si el scanner lo requiere)
                    # self.fvg_scanner.escanear_y_guardar(df_final, tf, dir_mapas)
            
            except Exception as e:
                self.log.registrar_error("DATA_MINER", f"Error procesando {tf}: {e}")

        return True

    def _sincronizar_master_1m(self):
        """
        Lógica de 'Gap Filling': Encuentra el hueco exacto y lo rellena.
        """
        path = os.path.join(self.base_dir, f"{Config.SYMBOL}_{self.master_tf}.csv")
        
        # Fecha por defecto: Hace 1 mes para no saturar si es nuevo
        start_ts = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)
        modo = "FULL_DOWNLOAD (Inicial)"
        
        # VERIFICACIÓN DE DATA EXISTENTE
        if os.path.exists(path):
            try:
                # Leemos solo las últimas lineas para ser eficientes
                df_check = pd.read_csv(path)
                if not df_check.empty and 'timestamp' in df_check.columns:
                    last_ts = int(df_check.iloc[-1]['timestamp'])
                    start_ts = last_ts + 60000 # +1 minuto
                    modo = "INCREMENTAL (Gap Fill)"
            except Exception:
                pass # Si falla, descarga completa

        # VERIFICAR SI ESTAMOS AL DÍA (Margen de 2 min)
        now_ts = int(time.time() * 1000)
        if (now_ts - start_ts) < 120000:
            return False # No hubo cambios

        self.log.registrar_actividad("DATA_MINER", f"📥 Descargando 1m | Modo: {modo}")

        # BUCLE DE DESCARGA PAGINADA
        current_ts = start_ts
        batch_size = 1000
        descarga_total = 0
        
        while current_ts < now_ts:
            # Usamos API Manager para obtener velas
            try:
                candles = self.api.client.klines(
                    symbol=Config.SYMBOL, 
                    interval=self.master_tf, 
                    limit=batch_size, 
                    startTime=current_ts
                )
            except Exception as e:
                self.log.registrar_error("DATA_MINER", f"API Fail: {e}")
                break
            
            if not candles: 
                break
            
            # Procesar datos
            data = []
            for c in candles:
                data.append({
                    'timestamp': c[0], 'open': float(c[1]), 'high': float(c[2]), 
                    'low': float(c[3]), 'close': float(c[4]), 'volume': float(c[5])
                })
            
            # Guardado inmediato (Append)
            df_batch = pd.DataFrame(data)
            es_archivo_nuevo = not os.path.exists(path)
            df_batch.to_csv(path, mode='a', header=es_archivo_nuevo, index=False)
            
            # Actualizar cursor
            last_candle_ts = data[-1]['timestamp']
            current_ts = last_candle_ts + 60000
            descarga_total += len(data)
            
            time.sleep(0.2) # Respetar rate limits

        if descarga_total > 0:
            self.log.registrar_actividad("DATA_MINER", f"✅ Sincronización finalizada. (+{descarga_total} velas)")
            return True
        return False

    def _guardar_csv(self, df, tf):
        path = os.path.join(self.base_dir, f"{Config.SYMBOL}_{tf}.csv")
        # Asegurar columnas limpias
        cols_base = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        cols = cols_base + [c for c in df.columns if c not in cols_base and c != 'datetime']
        df[cols].to_csv(path, index=False)

    def _verificar_derivados_existen(self):
        """Verifica si faltan archivos de temporalidades superiores."""
        for tf in self.target_tfs:
            path = os.path.join(self.base_dir, f"{Config.SYMBOL}_{tf}.csv")
            if not os.path.exists(path):
                return False 
        return True

    def obtener_dataframe_cache(self, tf):
        """Método crítico usado por Main para alimentar al Brain"""
        path = os.path.join(self.base_dir, f"{Config.SYMBOL}_{tf}.csv")
        if os.path.exists(path): 
            try:
                return pd.read_csv(path)
            except:
                return pd.DataFrame()
        return pd.DataFrame()