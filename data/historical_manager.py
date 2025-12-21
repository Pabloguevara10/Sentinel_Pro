import pandas as pd
import os
import time
from datetime import datetime, timedelta
from config.config import Config

# IMPORTACIONES DE HERRAMIENTAS
from data.calculator import Calculator
from tools.fvg_scanner import FVGScanner

class HistoricalManager:
    """
    GESTOR DE DATOS HISTÓRICOS (V12.4 - GAP FILLING INTELIGENTE):
    - Detecta data existente con precisión quirúrgica.
    - Solo descarga el diferencial (GAP) faltante.
    - Previene baneos de IP evitando descargas redundantes.
    """
    def __init__(self, api_manager, logger):
        self.api = api_manager
        self.log = logger
        self.base_dir = Config.DIR_DATA
        self.fvg_scanner = FVGScanner()
        
        self.master_tf = '1m'
        self.target_tfs = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d']

    def sincronizar_infraestructura_datos(self):
        # 1. SINCRONIZACIÓN QUIRÚRGICA DEL MAESTRO (1m)
        cambios_realizados = self._sincronizar_master_1m()
        
        # Si no hubo cambios (data estaba al día), no hace falta recalcular todo
        # a menos que sea el arranque inicial o queramos forzarlo.
        # Para seguridad, recalculamos temporalidades si hubo descarga o si faltan archivos derivados.
        if not cambios_realizados and self._verificar_derivados_existen():
            # self.log.registrar_actividad("DATA_MINER", "✅ Datos al día. No se requiere procesamiento.")
            return True

        self.log.registrar_actividad("DATA_MINER", "🔄 Procesando cascada de temporalidades...")

        # Cargar Master Actualizado
        path_master = os.path.join(self.base_dir, f"{Config.SYMBOL}_{self.master_tf}.csv")
        try:
            df_master = pd.read_csv(path_master)
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
                df_procesado = None
                if tf == '1m':
                    df_procesado = df_master.copy()
                else:
                    df_procesado = Calculator.resample_data(df_master, tf)

                if df_procesado is not None and not df_procesado.empty:
                    # Indicadores
                    df_final = Calculator.agregar_indicadores(df_procesado)
                    
                    # Guardar CSV Velas
                    self._guardar_csv(df_final, tf)
                    
                    # Generar FVG (CSV Legacy)
                    self.fvg_scanner.escanear_y_guardar(df_final, tf, dir_mapas)
            
            except Exception as e:
                self.log.registrar_error("DATA_MINER", f"Error procesando {tf}: {e}")

        return True

    def _sincronizar_master_1m(self):
        """
        Lógica de 'Gap Filling': Encuentra el hueco exacto y lo rellena.
        """
        path = os.path.join(self.base_dir, f"{Config.SYMBOL}_{self.master_tf}.csv")
        
        # Fecha por defecto: Hace 1 año
        start_ts = int((datetime.now() - timedelta(days=365)).timestamp() * 1000)
        modo = "FULL_DOWNLOAD (Inicial)"
        
        # VERIFICACIÓN DE DATA EXISTENTE
        if os.path.exists(path):
            try:
                # Leemos solo el final del archivo para ser rápidos, pero Pandas requiere leer todo.
                # Si el archivo es muy grande, esto tarda un poco, pero es seguro.
                df_check = pd.read_csv(path)
                
                if not df_check.empty and 'timestamp' in df_check.columns:
                    last_ts = int(df_check.iloc[-1]['timestamp'])
                    start_ts = last_ts + 60000 # +1 minuto
                    modo = "INCREMENTAL (Gap Fill)"
                    
                    # Debug visual
                    last_date = datetime.fromtimestamp(last_ts/1000)
                    # print(f"   [DEBUG] Último registro encontrado: {last_date}")
            except Exception as e:
                self.log.registrar_error("DATA_MINER", f"Archivo corrupto, se descargará todo: {e}")

        # VERIFICAR SI ESTAMOS AL DÍA
        now_ts = int(time.time() * 1000)
        # Si la diferencia es menor a 2 minutos (120000 ms), asumimos que está al día
        if (now_ts - start_ts) < 120000:
            return False # No hubo cambios

        self.log.registrar_actividad("DATA_MINER", f"📥 Descargando 1m | Modo: {modo}")
        # print(f"   ↳ Buscando velas desde: {datetime.fromtimestamp(start_ts/1000)}")

        # BUCLE DE DESCARGA (Paginación)
        current_ts = start_ts
        batch_size = 1000
        descarga_total = 0
        
        while current_ts < now_ts:
            candles = self.api.get_historical_candles(
                Config.SYMBOL, self.master_tf, limit=batch_size, start_time=current_ts
            )
            
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
            
            # Si es modo FULL y es el primer lote, header=True. Si es Incremental, header=False
            es_archivo_nuevo = not os.path.exists(path)
            df_batch.to_csv(path, mode='a', header=es_archivo_nuevo, index=False)
            
            # Actualizar cursor
            last_candle_ts = data[-1]['timestamp']
            current_ts = last_candle_ts + 60000
            descarga_total += len(data)
            
            # Feedback visual si la descarga es grande
            if descarga_total % 5000 == 0:
                fecha_actual = datetime.fromtimestamp(last_candle_ts/1000).strftime('%Y-%m-%d')
                print(f"      ⏳ Sincronizando... Vamos por: {fecha_actual}")
            
            time.sleep(0.2) # Pausa técnica

        self.log.registrar_actividad("DATA_MINER", f"✅ Sincronización finalizada. (+{descarga_total} velas)")
        return True

    def _guardar_csv(self, df, tf):
        path = os.path.join(self.base_dir, f"{Config.SYMBOL}_{tf}.csv")
        cols_base = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        cols = cols_base + [c for c in df.columns if c not in cols_base and c != 'datetime']
        df[cols].to_csv(path, index=False)

    def _verificar_derivados_existen(self):
        """Verifica si faltan archivos de temporalidades superiores."""
        for tf in self.target_tfs:
            path = os.path.join(self.base_dir, f"{Config.SYMBOL}_{tf}.csv")
            if not os.path.exists(path):
                return False # Falta uno, hay que procesar
        return True

    def obtener_dataframe_cache(self, tf):
        path = os.path.join(self.base_dir, f"{Config.SYMBOL}_{tf}.csv")
        if os.path.exists(path): return pd.read_csv(path)
        return pd.DataFrame()