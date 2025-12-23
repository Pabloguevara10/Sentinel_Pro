# =============================================================================
# NOMBRE: TrendSurfer_Sim.py
# DESCRIPCIÓN: 
#   Simulador de Estrategia "Pyramiding" (Escalado Seguro).
#   - Prueba la lógica de agregar capital en retrocesos de tendencias fuertes.
#   - Implementa "Safety Check" matemático antes de recargar.
#   - Ajusta SL dinámicamente al Nuevo Promedio + Profit.
# =============================================================================

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

# --- CONFIGURACIÓN ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
data_dir = os.path.join(project_root, 'data', 'historical')
reports_dir = os.path.join(project_root, 'reports')

if not os.path.exists(reports_dir): os.makedirs(reports_dir)

class SimConfig:
    SYMBOL = "AAVEUSDT"
    FILE_15M = os.path.join(data_dir, "AAVEUSDT_15m.csv")
    
    # Capital
    BASE_SIZE_USD = 100.0   # Tamaño de la entrada inicial
    ADD_SIZE_USD = 100.0    # Tamaño de cada recarga
    MAX_ADDS = 3            # Máximo número de recargas permitidas (Pyramiding)
    
    # Filtros de Tendencia
    MIN_ADX_ENTRY = 25      # Fuerza mínima para entrar
    MIN_ADX_ADD = 30        # Fuerza mínima para recargar (TrendSurfer)
    
    # Safety Check (Matemática de Protección)
    SAFETY_BUFFER_PCT = 0.006  # 0.6% de distancia mínima requerida tras promediar
    PROFIT_LOCK_PCT = 0.002    # 0.2% de ganancia asegurada al mover el SL
    
    # Precisión
    QTY_PRECISION = 1
    PRICE_PRECISION = 2

# --- LABORATORIO MOCKEADO ---
class MockPrecisionLab:
    @staticmethod
    def calcular_indicadores(df):
        df = df.copy()
        # EMAs
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        
        # ADX (Simplificado para simulación si no existe en data)
        # Si la data ya tiene ADX, usamos ese. Si no, calculamos uno básico.
        if 'adx' not in df.columns:
            df['adx'] = 50.0 # Mock por si falla lectura, pero tu CSV tiene ADX
            
        return df

# --- MOTOR DE SIMULACIÓN ---
class TrendSurferSimulator:
    def __init__(self):
        self.trades_history = []
        self.active_position = None # Solo una posición activa a la vez (Trend Following)
        self.lab = MockPrecisionLab()
        print(f"🌊 INICIANDO TREND SURFER SIMULATOR ({SimConfig.SYMBOL})")

    def cargar_datos(self):
        print("⏳ Cargando datos...")
        try:
            self.df = pd.read_csv(SimConfig.FILE_15M)
            self.df['datetime'] = pd.to_datetime(self.df['timestamp'], unit='ms')
            
            # Asegurar indicadores
            self.df = self.lab.calcular_indicadores(self.df)
            self.df.dropna(inplace=True)
            self.df.reset_index(drop=True, inplace=True)
            
            print(f"✅ Data cargada: {len(self.df)} velas.")
        except Exception as e:
            print(f"❌ Error cargando data: {e}")
            sys.exit(1)

    def _redondear(self, val, prec):
        fmt = "{:." + str(prec) + "f}"
        return float(fmt.format(val))

    def _ejecutar_simulacion(self):
        print("🚀 Surfeando tendencias...")
        
        for i, row in self.df.iterrows():
            if i < 20: continue # Warmup
            
            # 1. GESTIÓN DE POSICIÓN ACTIVA (Salidas y Recargas)
            if self.active_position:
                self._gestionar_posicion(row, self.df.iloc[i-1])
            
            # 2. BUSCAR NUEVA ENTRADA (Si no hay posición)
            else:
                self._buscar_entrada_base(row, self.df.iloc[i-1])

    def _buscar_entrada_base(self, row, prev_row):
        """Entrada clásica de cruce de medias con ADX"""
        adx = row.get('adx', 0)
        if adx < SimConfig.MIN_ADX_ENTRY: return
        
        # LONG: Cruce EMA 9 > EMA 21
        if row['ema_9'] > row['ema_21'] and prev_row['ema_9'] <= prev_row['ema_21']:
            self._abrir_posicion('LONG', row)
            
        # SHORT: Cruce EMA 9 < EMA 21
        elif row['ema_9'] < row['ema_21'] and prev_row['ema_9'] >= prev_row['ema_21']:
            self._abrir_posicion('SHORT', row)

    def _abrir_posicion(self, side, row):
        price = row['close']
        qty = self._redondear(SimConfig.BASE_SIZE_USD / price, SimConfig.QTY_PRECISION)
        
        # SL Inicial (Swing Low/High simple o % fijo por ahora)
        sl = price * 0.98 if side == 'LONG' else price * 1.02
        
        self.active_position = {
            'id': f"TS_{int(row['timestamp'])}",
            'side': side,
            'entry_price': price,   # Promedio
            'qty': qty,
            'sl_price': sl,
            'entry_time': row['datetime'],
            'adds_count': 0,
            'status': 'OPEN',
            'max_pnl_pct': 0.0
        }
        # print(f"  🏁 NEW {side} @ {price}")

    def _gestionar_posicion(self, row, prev_row):
        pos = self.active_position
        price = row['close']
        high = row['high']
        low = row['low']
        
        # A. VERIFICAR STOP LOSS / TRAILING STOP
        stop_hit = False
        exit_price = 0.0
        
        if pos['side'] == 'LONG':
            if low <= pos['sl_price']:
                stop_hit = True
                exit_price = pos['sl_price']
        else: # SHORT
            if high >= pos['sl_price']:
                stop_hit = True
                exit_price = pos['sl_price']
                
        if stop_hit:
            self._cerrar_posicion(pos, row['datetime'], exit_price, "SL_HIT")
            return

        # B. INTENTO DE PYRAMIDING (Recarga)
        # Solo si tenemos cupo y tendencia fuerte
        if pos['adds_count'] < SimConfig.MAX_ADDS and row.get('adx', 0) > SimConfig.MIN_ADX_ADD:
            self._evaluar_recarga(pos, row, prev_row)
            
        # C. ACTUALIZAR MÉTRICAS (Trailing simple si no hay recarga)
        # Aquí podríamos poner un trailing normal, pero el foco es el pyramiding logic.

    def _evaluar_recarga(self, pos, row, prev_row):
        """Lógica TREND SURFER: Agregar en Pullback validado"""
        price = row['close']
        ema_9 = row['ema_9']
        ema_21 = row['ema_21']
        
        is_pullback = False
        
        # Detección de Pullback: El precio tocó la EMA pero cerró a favor
        if pos['side'] == 'LONG':
            # Tocó la EMA9 o EMA21 en el Low, pero cerró arriba (Rebote)
            if row['low'] <= ema_9 and price > ema_9:
                is_pullback = True
        else: # SHORT
            if row['high'] >= ema_9 and price < ema_9:
                is_pullback = True
                
        if not is_pullback: return

        # --- SAFETY CHECK (EL CORAZÓN DEL ALGORITMO) ---
        
        # 1. Simular Nuevo Promedio
        new_qty = self._redondear(SimConfig.ADD_SIZE_USD / price, SimConfig.QTY_PRECISION)
        total_qty = pos['qty'] + new_qty
        
        current_value = pos['qty'] * pos['entry_price'] # Costo histórico
        new_add_value = new_qty * price
        
        new_avg_price = (current_value + new_add_value) / total_qty
        
        # 2. Verificar Margen de Seguridad
        dist_safety = 0.0
        if pos['side'] == 'LONG':
            # El precio actual debe estar ARRIBA del nuevo promedio
            dist_safety = (price - new_avg_price) / new_avg_price
        else:
            # El precio actual debe estar ABAJO del nuevo promedio
            dist_safety = (new_avg_price - price) / new_avg_price
            
        if dist_safety < SimConfig.SAFETY_BUFFER_PCT:
            # print(f"    ⚠️ RECARGA RECHAZADA: Margen {dist_safety:.2%} < {SimConfig.SAFETY_BUFFER_PCT:.2%}")
            return # ABORTAR: Demasiado arriesgado
            
        # 3. EJECUTAR RECARGA
        pos['qty'] = total_qty
        pos['entry_price'] = new_avg_price
        pos['adds_count'] += 1
        
        # 4. AJUSTAR SL (Profit Lock)
        # Ponemos el SL en el Nuevo Promedio +/- un pequeño profit asegurado
        if pos['side'] == 'LONG':
            pos['sl_price'] = new_avg_price * (1 + SimConfig.PROFIT_LOCK_PCT)
        else:
            pos['sl_price'] = new_avg_price * (1 - SimConfig.PROFIT_LOCK_PCT)
            
        # print(f"    🚀 PYRAMIDING #{pos['adds_count']}! Avg: {new_avg_price:.2f} | New SL: {pos['sl_price']:.2f}")

    def _cerrar_posicion(self, pos, time, price, reason):
        # Calcular PnL Real
        entry = pos['entry_price']
        qty = pos['qty']
        
        if pos['side'] == 'LONG':
            pnl = (price - entry) * qty
            pnl_pct = (price - entry) / entry
        else:
            pnl = (entry - price) * qty
            pnl_pct = (entry - price) / entry
            
        record = {
            'ID': pos['id'],
            'Side': pos['side'],
            'Entry_Time': pos['entry_time'],
            'Exit_Time': time,
            'Avg_Entry': entry,
            'Exit_Price': price,
            'Max_Adds': pos['adds_count'], # Cuántas veces recargamos
            'PnL_USD': round(pnl, 2),
            'PnL_Pct': round(pnl_pct*100, 2),
            'Reason': reason
        }
        self.trades_history.append(record)
        self.active_position = None

    def generar_reporte(self):
        if not self.trades_history:
            print("⚠️ No se generaron operaciones.")
            return
            
        df = pd.DataFrame(self.trades_history)
        
        print("\n" + "="*40)
        print(f"🌊 RESULTADOS TREND SURFER ({SimConfig.SYMBOL})")
        print("="*40)
        print(f"Total Operaciones: {len(df)}")
        print(f"PnL Total:         ${df['PnL_USD'].sum():.2f}")
        
        # Métricas de Pyramiding
        trades_with_adds = df[df['Max_Adds'] > 0]
        print(f"Ops con Recargas:  {len(trades_with_adds)} ({len(trades_with_adds)/len(df)*100:.1f}%)")
        if not trades_with_adds.empty:
            print(f"PnL en Recargas:   ${trades_with_adds['PnL_USD'].sum():.2f}")
            
        filename = f"TrendSurfer_AUDIT_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        path = os.path.join(reports_dir, filename)
        df.to_csv(path, index=False)
        print(f"\n📄 Reporte guardado en: {path}")

if __name__ == "__main__":
    sim = TrendSurferSimulator()
    sim.cargar_datos()
    sim._ejecutar_simulacion()
    sim.generar_reporte()