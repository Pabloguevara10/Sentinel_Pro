import pandas as pd
import os
import sys
from datetime import datetime

# Ajuste de rutas
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import Config

class FVGScanner:
    """
    ESCANER DE FVG INTELIGENTE (Incremental):
    Genera y mantiene actualizados los mapas de Fair Value Gaps.
    No recalcula el pasado; solo anexa nuevas zonas detectadas.
    """
    def __init__(self):
        self.cfg = Config()
        self.timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d']
        self.output_dir = os.path.join(self.cfg.DIR_DATA, 'mapas_fvg')
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def escanear_todo(self):
        print(f"\n🗺️ INICIANDO CARTOGRAFÍA FVG INCREMENTAL ({self.cfg.SYMBOL})...")
        
        for tf in self.timeframes:
            self._procesar_temporalidad(tf)
            
        print("\n✅ Mapas actualizados en:", self.output_dir)

    def _procesar_temporalidad(self, tf):
        # 1. Definir Rutas
        price_file = os.path.join(self.cfg.DIR_DATA, f"{self.cfg.SYMBOL}_{tf}.csv")
        map_file = os.path.join(self.output_dir, f"mapa_fvg_{tf}.csv")
        
        if not os.path.exists(price_file):
            print(f"⚠️ Saltando {tf}: No hay data de precios.")
            return

        # 2. Cargar Mapa Existente (si hay)
        existing_fvgs = []
        last_ts = 0
        
        if os.path.exists(map_file):
            try:
                df_map = pd.read_csv(map_file)
                if not df_map.empty and 'created_at' in df_map.columns:
                    last_ts = int(df_map['created_at'].max())
                    existing_fvgs = df_map.to_dict('records')
                    print(f"   🔄 {tf}: Actualizando desde {datetime.fromtimestamp(last_ts/1000)}")
            except:
                print(f"   ⚠️ {tf}: Error leyendo mapa anterior. Se regenerará.")

        if last_ts == 0:
            print(f"   🆕 {tf}: Generando mapa desde cero...")

        # 3. Cargar Precios
        df_price = pd.read_csv(price_file)
        
        # 4. Optimización: Filtrar Data Nueva
        # Buscamos el índice donde la data es nueva.
        # FVG se forma con velas A, B, C. 'created_at' es el cierre de C.
        # Necesitamos empezar a escanear un poco antes para capturar el patrón en la frontera.
        
        start_index = 1
        if last_ts > 0:
            # Buscamos velas posteriores al último FVG conocido
            nuevas_velas = df_price[df_price['timestamp'] > last_ts]
            if nuevas_velas.empty:
                print(f"      ✅ {tf}: Mapa ya está al día.")
                return
            
            # Retrocedemos 2 velas desde la primera nueva para tener contexto (A, B, C)
            first_new_idx = nuevas_velas.index[0]
            start_index = max(1, first_new_idx - 1)

        # 5. Escaneo (Loop Principal)
        new_fvgs = []
        count_added = 0
        
        for i in range(start_index, len(df_price) - 1):
            # Indices: A(i-1), B(i)=Gap, C(i+1)=Confirmación
            idx_a = i - 1
            idx_c = i + 1
            
            row_a = df_price.iloc[idx_a]
            row_c = df_price.iloc[idx_c]
            
            # Solo procesar si la vela C es posterior a lo que ya teníamos
            if row_c['timestamp'] <= last_ts:
                continue

            high_a, low_a = row_a['high'], row_a['low']
            high_c, low_c = row_c['high'], row_c['low']
            ts_created = int(row_c['timestamp'])
            
            # FVG ALCISTA (Bullish): Low C > High A
            if low_c > high_a:
                fvg = {
                    'id_fvg': f"{tf}_{ts_created}", # ID único basado en tiempo
                    'type': 'BULLISH',
                    'top': low_c,
                    'bottom': high_a,
                    'created_at': ts_created,
                    'filled': False
                }
                new_fvgs.append(fvg)
                count_added += 1
                
            # FVG BAJISTA (Bearish): High C < Low A
            elif high_c < low_a:
                fvg = {
                    'id_fvg': f"{tf}_{ts_created}",
                    'type': 'BEARISH',
                    'top': low_a,
                    'bottom': high_c,
                    'created_at': ts_created,
                    'filled': False
                }
                new_fvgs.append(fvg)
                count_added += 1

        # 6. Guardar Resultados
        if new_fvgs:
            all_fvgs = existing_fvgs + new_fvgs
            df_final = pd.DataFrame(all_fvgs)
            # Eliminar duplicados por si acaso
            df_final.drop_duplicates(subset='id_fvg', keep='last', inplace=True)
            
            df_final.to_csv(map_file, index=False)
            print(f"      💾 {tf}: +{count_added} zonas nuevas agregadas.")
        elif last_ts == 0:
            print(f"      ⚪ {tf}: No se encontraron zonas.")

if __name__ == "__main__":
    scanner = FVGScanner()
    scanner.escanear_todo()