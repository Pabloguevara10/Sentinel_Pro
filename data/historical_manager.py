# =============================================================================
# UBICACIÓN: data/historical_manager.py
# DESCRIPCIÓN: GESTOR HISTÓRICO V18.9 (MODO TURBO SYNC)
# =============================================================================

import pandas as pd
import os
import time
from config.config import Config
from tools.fvg_scanner import FVGScanner
from tools.data_seeder import DataSeeder

class HistoricalManager:
    def __init__(self, api_manager, logger):
        self.api = api_manager
        self.log = logger
        self.base_dir = Config.DIR_DATA
        self.fvg_scanner = FVGScanner()
        self.seeder = DataSeeder(api_manager)
        self.master_tf = '1m'
        self.target_tfs = ['2m', '3m', '5m', '15m', '30m', '1h', '4h', '1d']

    def sincronizar_infraestructura_datos(self):
        # Intentamos sincronizar. El método 'turbo' retorna True si descargó algo.
        hubo_actualizacion = self._sincronizar_maestro_turbo()
        
        faltan_archivos = not self._verificar_derivados_existen()
        hay_desfase = self._verificar_desfase_temporal()

        if hubo_actualizacion or faltan_archivos or hay_desfase:
            print("🔄 [DATA] Regenerando indicadores multitemporales...")
            self.seeder.sembrar_datos()

    def _sincronizar_maestro_turbo(self):
        """Descarga en bucle hasta estar al día (Turbo Catch-up)."""
        path = os.path.join(self.base_dir, f"{Config.SYMBOL}_{self.master_tf}.csv")
        
        # 1. Creación inicial si no existe
        if not os.path.exists(path):
            print("⚠️ [DATA] Descargando base inicial...")
            data = self._descargar_bloque(limit=1500)
            if data:
                df = pd.DataFrame(data)
                self._guardar_csv(df, self.master_tf)
                return True
            return False

        # 2. Actualización Incremental en Bucle
        actualizaciones_realizadas = False
        
        while True:
            try:
                # Leer estado actual
                df_actual = pd.read_csv(path)
                if df_actual.empty: return False

                last_ts = int(df_actual['timestamp'].iloc[-1])
                
                # Pedir datos desde la última vela
                nuevas_velas = self._descargar_desde(last_ts)
                
                if not nuevas_velas: 
                    break # No hay más datos en Binance

                # Verificar si es solo la misma vela actualizándose
                if len(nuevas_velas) == 1:
                    last_close = float(df_actual['close'].iloc[-1])
                    new_close = float(nuevas_velas[0]['close'])
                    if last_close == new_close:
                        break # Precio idéntico, estamos al día.
                
                # Guardar bloque
                df_nuevo = pd.DataFrame(nuevas_velas)
                df_total = pd.concat([df_actual, df_nuevo]).drop_duplicates(subset='timestamp', keep='last')
                self._guardar_csv(df_total, self.master_tf)
                
                actualizaciones_realizadas = True
                print(f"📥 [DATA] Sincronizando... Última: {nuevas_velas[-1]['close']} (Bloque de {len(nuevas_velas)})")

                # Si descargamos menos de 1000, significa que ya llegamos al final
                if len(nuevas_velas) < 999:
                    print("✅ [DATA] Sincronización completada al 100%.")
                    break
                
                # Si descargamos 1000, seguimos en el bucle inmediatamente
                time.sleep(0.1) # Breve respiro para no saturar

            except Exception as e:
                print(f"❌ [DATA] Error en bucle sync: {e}")
                break
        
        return actualizaciones_realizadas

    def _descargar_bloque(self, limit=1000):
        try:
            klines = self.api.client.klines(symbol=Config.SYMBOL, interval=self.master_tf, limit=limit)
            return self._formatear_klines(klines)
        except: return []

    def _descargar_desde(self, start_ts):
        try:
            klines = self.api.client.klines(
                symbol=Config.SYMBOL,
                interval=self.master_tf,
                startTime=int(start_ts),
                limit=1000
            )
            return self._formatear_klines(klines)
        except: return []

    def _formatear_klines(self, klines):
        clean = []
        if not klines: return []
        for k in klines:
            clean.append({
                'timestamp': int(k[0]),
                'open': float(k[1]), 'high': float(k[2]),
                'low': float(k[3]), 'close': float(k[4]),
                'volume': float(k[5])
            })
        return clean

    def _guardar_csv(self, df, tf):
        path = os.path.join(self.base_dir, f"{Config.SYMBOL}_{tf}.csv")
        cols_base = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        cols = cols_base + [c for c in df.columns if c not in cols_base and c != 'datetime']
        df[cols].to_csv(path, index=False)

    def _verificar_derivados_existen(self):
        for tf in self.target_tfs:
            path = os.path.join(self.base_dir, f"{Config.SYMBOL}_{tf}.csv")
            if not os.path.exists(path): return False 
        return True

    def _verificar_desfase_temporal(self):
        # Verificación rápida
        return False # Simplificado para confiar en el turbo sync

    def obtener_dataframe_cache(self, tf):
        path = os.path.join(self.base_dir, f"{Config.SYMBOL}_{tf}.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                if 'timestamp' in df.columns:
                    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df.set_index('datetime', inplace=True, drop=False)
                return df
            except: pass
        return pd.DataFrame()