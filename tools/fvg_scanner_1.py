import pandas as pd
import os

class FVGScanner:
    """
    ESCANER DE FVG (V12.2 - COMPATIBILIDAD LEGACY):
    - Detecta FVGs.
    - Guarda en formato CSV con nomenclatura 'mapa_fvg_{tf}.csv'.
    """
    
    def escanear_y_guardar(self, df, timeframe, output_dir):
        """
        Escanea el DF y guarda el resultado en la carpeta especificada.
        Formato de salida: CSV (Compatible con Brain legacy).
        """
        fvgs = self._detectar_fvgs(df)
        
        # Nomenclatura Legacy: mapa_fvg_5m.csv
        filename = f"mapa_fvg_{timeframe}.csv"
        path = os.path.join(output_dir, filename)
        
        try:
            if fvgs:
                df_fvg = pd.DataFrame(fvgs)
                df_fvg.to_csv(path, index=False)
            else:
                # Si no hay FVGs, creamos un CSV vacío con cabeceras para no romper el lector
                pd.DataFrame(columns=['id', 'type', 'top', 'bottom', 'size', 'timestamp', 'mitigated']).to_csv(path, index=False)
                
        except Exception as e:
            print(f"Error guardando FVG {timeframe}: {e}")

    def _detectar_fvgs(self, df):
        """
        Lógica de detección de gaps.
        """
        fvgs = []
        records = df.to_dict('records')
        
        # Iteramos hacia atrás
        for i in range(len(records) - 1, 1, -1):
            curr = records[i]     # Vela i
            prev = records[i-2]   # Vela i-2
            ts = curr.get('timestamp')
            
            # FVG ALCISTA (Bullish)
            if curr['low'] > prev['high']:
                gap_size = curr['low'] - prev['high']
                fvgs.append({
                    'id': int(ts), 
                    'type': 'BULLISH',
                    'top': curr['low'],
                    'bottom': prev['high'],
                    'size': gap_size,
                    'timestamp': int(ts),
                    'mitigated': False 
                })

            # FVG BAJISTA (Bearish)
            elif curr['high'] < prev['low']:
                gap_size = prev['low'] - curr['high']
                fvgs.append({
                    'id': int(ts),
                    'type': 'BEARISH',
                    'top': prev['low'],
                    'bottom': curr['high'],
                    'size': gap_size,
                    'timestamp': int(ts),
                    'mitigated': False
                })
                
            if len(fvgs) >= 200: # Límite de seguridad
                break
                
        return fvgs