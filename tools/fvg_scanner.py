import pandas as pd
import os
import sys

# Ajuste de rutas para importar configuración y logs
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import Config
from logs.system_logger import SystemLogger

class FVGScanner:
    """
    ESCÁNER DE FAIR VALUE GAPS (V2.0 - INTEGRADO):
    - Escanea patrones de ineficiencia (FVG) de forma incremental.
    - Se integra con el Sistema de Logs del Bot.
    """
    def __init__(self):
        self.cfg = Config()
        self.log = SystemLogger()
        
        # Carpeta de salida
        self.output_dir = os.path.join(self.cfg.DIR_DATA, 'mapas_fvg')
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        # Temporalidades a escanear (Coherentes con el Seeder)
        self.timeframes = ['5m', '15m', '1h', '4h']

    def escanear_todo(self):
        """Método maestro llamado por Main."""
        cambios_totales = 0
        
        for tf in self.timeframes:
            n_nuevos = self._procesar_temporalidad(tf)
            cambios_totales += n_nuevos
            
        if cambios_totales > 0:
            self.log.registrar_actividad("FVG_SCANNER", f"🗺️ Mapas actualizados. {cambios_totales} zonas nuevas detectadas.")

    def _procesar_temporalidad(self, tf):
        """Lógica incremental por temporalidad."""
        try:
            # 1. Rutas de archivos
            price_file = os.path.join(self.cfg.DIR_DATA, f"{self.cfg.SYMBOL}_{tf}.csv")
            map_file = os.path.join(self.output_dir, f"mapa_fvg_{tf}.csv")
            
            if not os.path.exists(price_file):
                return 0

            # 2. Cargar precios
            df_price = pd.read_csv(price_file)
            if df_price.empty: return 0

            # 3. Determinar punto de partida (Incremental)
            existing_fvgs = []
            last_fvg_time = 0
            
            if os.path.exists(map_file):
                try:
                    df_map = pd.read_csv(map_file)
                    if not df_map.empty:
                        existing_fvgs = df_map.to_dict('records')
                        last_fvg_time = df_map.iloc[-1]['created_at']
                except Exception:
                    pass # Si falla lectura, asumimos cero

            # 4. Filtrar datos nuevos
            # Solo analizamos velas posteriores al último FVG conocido
            df_new = df_price[df_price['timestamp'] > last_fvg_time].reset_index(drop=True)
            
            # Necesitamos al menos 3 velas para formar un FVG
            if len(df_new) < 3:
                return 0

            # 5. Detección de Patrones
            new_fvgs = []
            
            # Iteramos buscando el patrón de 3 velas (i-2, i-1, i)
            # Empezamos en índice 2 (tercera vela)
            for i in range(2, len(df_new)):
                candle_c = df_new.iloc[i]     # Vela actual
                # candle_b = df_new.iloc[i-1] # Vela medio (Gap)
                candle_a = df_new.iloc[i-2]   # Vela origen
                
                # FVG ALCISTA (Bullish)
                # Hueco entre High de A y Low de C
                if candle_c['low'] > candle_a['high']:
                    fvg = {
                        'id': f"{tf}_{int(candle_c['timestamp'])}_BULL",
                        'created_at': int(candle_c['timestamp']),
                        'type': 'BULLISH',
                        'top': float(candle_c['low']),
                        'bottom': float(candle_a['high']),
                        'mitigated': False,
                        'mitigated_at': 0
                    }
                    new_fvgs.append(fvg)

                # FVG BAJISTA (Bearish)
                # Hueco entre Low de A y High de C
                elif candle_c['high'] < candle_a['low']:
                    fvg = {
                        'id': f"{tf}_{int(candle_c['timestamp'])}_BEAR",
                        'created_at': int(candle_c['timestamp']),
                        'type': 'BEARISH',
                        'top': float(candle_a['low']),
                        'bottom': float(candle_c['high']),
                        'mitigated': False,
                        'mitigated_at': 0
                    }
                    new_fvgs.append(fvg)

            # 6. Guardado (Solo si hay novedades)
            if new_fvgs:
                all_fvgs = existing_fvgs + new_fvgs
                df_final = pd.DataFrame(all_fvgs)
                df_final.to_csv(map_file, index=False)
                return len(new_fvgs)
            
            return 0

        except Exception as e:
            self.log.registrar_error("FVG_SCANNER", f"Error en {tf}: {e}")
            return 0