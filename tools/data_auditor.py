# =============================================================================
# UBICACIÓN: tools/data_auditor.py
# DESCRIPCIÓN: AUDITOR FORENSE DE DATA HISTÓRICA (FIX RUTAS)
# USO: python tools/data_auditor.py
# =============================================================================

import sys
import os

# --- FIX DE RUTAS: Agregar raíz del proyecto al Path ---
# Esto permite encontrar el módulo 'config' estando dentro de 'tools'
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)
# -------------------------------------------------------

import pandas as pd
import time
from datetime import datetime
from config.config import Config

class DataAuditor:
    def __init__(self):
        self.data_dir = Config.DIR_DATA
        self.symbol = Config.SYMBOL
        # Mapeo de intervalos a milisegundos
        self.tf_ms_map = {
            '1m': 60000,
            '3m': 180000,
            '5m': 300000,
            '15m': 900000,
            '30m': 1800000,
            '1h': 3600000,
            '4h': 14400000,
            '1d': 86400000
        }

    def auditar_todo(self):
        """Ejecuta la auditoría completa de todas las temporalidades."""
        print(f"\n🔍 INICIANDO AUDITORÍA FORENSE PARA {self.symbol}...")
        print("="*70)
        
        reporte_general = True
        
        # 1. Auditar la SEMILLA (1m) - Prioridad Crítica
        print(f"📂 Auditando MASTER (1m)...")
        estado_1m = self._auditar_archivo('1m', critico=True)
        if not estado_1m:
            reporte_general = False
            print("❌ LA DATA MAESTRA (1m) ESTÁ DAÑADA. SE REQUIERE INTERVENCIÓN.")
        
        print("-" * 70)

        # 2. Auditar DERIVADOS (Solo informativo)
        tfs_derivados = [tf for tf in Config.TIMEFRAMES if tf != '1m']
        for tf in tfs_derivados:
            print(f"📂 Auditando Derivado ({tf})...")
            estado = self._auditar_archivo(tf, critico=False)
            if not estado:
                print(f"   ⚠️  Recomendación: El archivo {tf} debería ser regenerado.")
        
        print("="*70)
        if reporte_general:
            print("✅ DIAGNÓSTICO: La estructura de datos es saludable.")
        else:
            print("⚠️ DIAGNÓSTICO: Se encontraron errores que requieren atención.")

    def _auditar_archivo(self, tf, critico=False):
        filename = f"{self.symbol}_{tf}.csv"
        path = os.path.join(self.data_dir, filename)
        
        # A. Existencia
        if not os.path.exists(path):
            print(f"   ❌ NO EXISTE: {filename}")
            return False
            
        try:
            # B. Lectura e Integridad
            df = pd.read_csv(path)
            if df.empty:
                print(f"   ❌ ARCHIVO VACÍO: {filename}")
                return False
                
            if 'timestamp' not in df.columns:
                print(f"   ❌ FORMATO INVÁLIDO (Sin columna timestamp)")
                return False

            # C. Análisis de Continuidad
            df['ts_diff'] = df['timestamp'].diff()
            expected_diff = self.tf_ms_map.get(tf, 60000)
            
            # Buscamos saltos mayores al esperado (Gaps)
            # Tolerancia pequeña de 1ms por errores de redondeo
            gaps = df[df['ts_diff'] > expected_diff]
            
            # Buscamos duplicados o retrocesos (Diff <= 0)
            errores_seq = df[df['ts_diff'] <= 0]
            
            total_velas = len(df)
            inicio = pd.to_datetime(df.iloc[0]['timestamp'], unit='ms')
            fin = pd.to_datetime(df.iloc[-1]['timestamp'], unit='ms')
            
            print(f"   ℹ️  Velas: {total_velas:,} | Desde: {inicio} | Hasta: {fin}")
            
            es_valido = True
            
            # REPORTE DE ERRORES
            if not errores_seq.empty:
                print(f"   ❌ ERRORES DE SECUENCIA: {len(errores_seq)} registros duplicados o desordenados.")
                try:
                    print(f"       Ejemplo: {pd.to_datetime(errores_seq.iloc[0]['timestamp'], unit='ms')}")
                except: pass
                es_valido = False
                
            if not gaps.empty:
                num_gaps = len(gaps)
                print(f"   ⚠️  HUECOS (GAPS) DETECTADOS: {num_gaps}")
                # Mostrar los primeros 3 gaps
                for idx, row in gaps.head(3).iterrows():
                    ts_gap = row['timestamp']
                    gap_time = pd.to_datetime(ts_gap, unit='ms')
                    print(f"       -> Salto en: {gap_time}")
                
                if critico:
                    print("       (Para 1m, estos huecos afectan los indicadores)")
            
            if es_valido and gaps.empty:
                print(f"   ✅ INTEGRIDAD PERFECTA")
            elif es_valido and not gaps.empty:
                print(f"   ⚠️  INTEGRIDAD OK (Con huecos temporales)")
                
            return es_valido

        except Exception as e:
            print(f"   ❌ CORRUPCIÓN CRÍTICA: No se puede leer el archivo ({e})")
            return False

if __name__ == "__main__":
    auditor = DataAuditor()
    auditor.auditar_todo()