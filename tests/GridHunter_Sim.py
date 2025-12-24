# =============================================================================
# NOMBRE: GridHunter_Sim.py (V2 - Refined)
# DESCRIPCIÓN: 
#   Simulador de Estrategia "Elastic Grid" con Reserva de Valor (Runner).
#   - AJUSTE V2: Mayor agresividad (BB 1.8) y Protección de Rentabilidad.
#   - Opera con datos históricos CSV (Sin conexión a Binance).
# =============================================================================

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

# --- CONFIGURACIÓN DE RUTAS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
data_dir = os.path.join(project_root, 'data', 'historical')
reports_dir = os.path.join(project_root, 'reports')

if not os.path.exists(reports_dir): os.makedirs(reports_dir)

# --- CLASE DE CONFIGURACIÓN SIMULADA ---
class SimConfig:
    # Activo
    SYMBOL = "AAVEUSDT"
    QTY_PRECISION = 1     
    PRICE_PRECISION = 2   
    MIN_QTY = 0.1
    
    # Archivos de Data
    FILE_15M = os.path.join(data_dir, "AAVEUSDT_15m.csv")
    
    # --- PARÁMETROS GRIDHUNTER V2 ---
    BB_PERIOD = 20
    BB_STD_DEV = 1.8         # <--- AJUSTE 1: Bajamos de 2.0 a 1.8 para más entradas
    
    # Gestión de Entradas
    GRID_LEVELS = 5          
    GRID_STEP_ATR_MULT = 0.5 
    
    # Gestión de Salidas y Runner
    TAKE_PROFIT_PCT = 0.60   # Vender el 60% al objetivo
    RUNNER_PCT = 0.40        # Dejar el 40% corriendo
    
    # Lotes (Asimetría)
    BASE_RISK_USD = 100.0    
    TREND_BIAS_RATIO = 1.0   
    COUNTER_BIAS_RATIO = 0.6 # <--- AJUSTE: Subimos un poco el riesgo en contra (0.5 -> 0.6)

# --- HERRAMIENTAS MOCKEADAS ---

class MockPrecisionLab:
    @staticmethod
    def calcular_bollinger(df, period=20, std_dev=2.0):
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, sma, lower

    @staticmethod
    def calcular_atr(df, period=14):
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        tr1 = high - low
        tr2 = (high - close).abs()
        tr3 = (low - close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

# --- MOTOR DEL SIMULADOR ---

class GridHunterSimulator:
    def __init__(self):
        self.trades_history = []
        self.active_grids = [] 
        self.lab = MockPrecisionLab()
        print(f"🤖 INICIANDO SIMULADOR GRIDHUNTER V2 (Aggressive) PARA {SimConfig.SYMBOL}")

    def cargar_datos(self):
        print("⏳ Cargando datos históricos...")
        try:
            self.df = pd.read_csv(SimConfig.FILE_15M)
            self.df['datetime'] = pd.to_datetime(self.df['timestamp'], unit='ms')
            
            # Calculamos indicadores con la nueva Desviación
            self.df['bb_upper'], self.df['bb_mid'], self.df['bb_lower'] = \
                self.lab.calcular_bollinger(self.df, SimConfig.BB_PERIOD, SimConfig.BB_STD_DEV)
            self.df['atr'] = self.lab.calcular_atr(self.df)
            
            self.df.dropna(inplace=True)
            self.df.reset_index(drop=True, inplace=True)
            
            print(f"✅ Datos listos: {len(self.df)} velas de 15m cargadas.")
            
        except FileNotFoundError:
            print("❌ Error: No se encuentran los archivos CSV en data/historical/")
            sys.exit(1)

    def _redondear_qty(self, qty):
        fmt = "{:." + str(SimConfig.QTY_PRECISION) + "f}"
        return float(fmt.format(qty))

    def _ejecutar_simulacion(self):
        print("🚀 Ejecutando simulación de mercado...")
        
        # Simulamos tendencia simple (Precio vs EMA200/Mid)
        trend_direction = 'NEUTRAL' 
        
        for i, row in self.df.iterrows():
            current_price = row['close']
            
            # 1. GESTIONAR POSICIONES (Salidas)
            self._gestionar_posiciones(row)
            
            # 2. DEFINIR TENDENCIA
            if current_price > row['bb_mid']: trend_direction = 'BULLISH'
            else: trend_direction = 'BEARISH'
            
            # 3. BUSCAR ENTRADAS
            self._buscar_entradas(row, trend_direction)

    def _buscar_entradas(self, row, trend):
        price = row['close']
        upper = row['bb_upper']
        lower = row['bb_lower']
        atr = row['atr']
        
        # --- LOGICA SHORT (Toque arriba) ---
        if row['high'] >= upper:
            if not self._existe_orden_cercana('SHORT', price, atr):
                qty_calc = (SimConfig.BASE_RISK_USD / price)
                # Asimetría
                if trend == 'BEARISH': qty_calc *= SimConfig.TREND_BIAS_RATIO
                else: qty_calc *= SimConfig.COUNTER_BIAS_RATIO
                
                self._abrir_orden('SHORT', price, qty_calc, row, "BB_TOUCH_UPPER")

        # --- LOGICA LONG (Toque abajo) ---
        if row['low'] <= lower:
            if not self._existe_orden_cercana('LONG', price, atr):
                qty_calc = (SimConfig.BASE_RISK_USD / price)
                # Asimetría
                if trend == 'BULLISH': qty_calc *= SimConfig.TREND_BIAS_RATIO
                else: qty_calc *= SimConfig.COUNTER_BIAS_RATIO
                
                self._abrir_orden('LONG', price, qty_calc, row, "BB_TOUCH_LOWER")

    def _existe_orden_cercana(self, side, price, atr):
        # ATR Step para no saturar
        min_dist = atr * SimConfig.GRID_STEP_ATR_MULT
        for grid in self.active_grids:
            if grid['side'] == side and grid['status'] == 'OPEN':
                if abs(grid['entry_price'] - price) < min_dist:
                    return True
        return False

    def _abrir_orden(self, side, price, qty, row, reason):
        qty = self._redondear_qty(qty)
        if qty < SimConfig.MIN_QTY: return
        
        grid_id = f"G_{int(row['timestamp']/1000)}"
        
        order = {
            'id': grid_id,
            'entry_time': row['datetime'],
            'entry_price': price,
            'side': side,
            'qty_total': qty,
            'qty_left': qty,
            'status': 'OPEN',
            'tp_hit': False,
            'runner_active': False,
            'max_price': price,
            'min_price': price
        }
        self.active_grids.append(order)

    def _gestionar_posiciones(self, row):
        """
        Revisa TP y Runner.
        AJUSTE V2: Profit Protection Check.
        """
        current_price = row['close']
        bb_mid = row['bb_mid']
        
        for grid in self.active_grids:
            if grid['status'] != 'OPEN': continue
            
            # Drawdown tracker
            if row['high'] > grid['max_price']: grid['max_price'] = row['high']
            if row['low'] < grid['min_price']: grid['min_price'] = row['low']
            
            # --- LOGICA LONG ---
            if grid['side'] == 'LONG':
                # Condición 1: Tocar Banda Media
                if not grid['tp_hit'] and row['high'] >= bb_mid:
                    
                    # <--- AJUSTE CRÍTICO 2: PROTECCIÓN DE RENTABILIDAD --->
                    # Solo cerramos si la Banda Media está por ENCIMA de nuestra entrada (Ganancia)
                    # Si no, esperamos (Hold) aunque hayamos tocado la media.
                    if bb_mid > grid['entry_price']:
                        close_qty = self._redondear_qty(grid['qty_total'] * SimConfig.TAKE_PROFIT_PCT)
                        self._registrar_trade(grid, row['datetime'], bb_mid, close_qty, "TP_MAIN_MID")
                        
                        grid['qty_left'] -= close_qty
                        grid['tp_hit'] = True
                        grid['runner_active'] = True 
                
                # Gestión del Runner (Reserva)
                elif grid['runner_active']:
                    # BE estricto: Si vuelve a caer al precio de entrada, cerramos lo que queda.
                    if row['low'] < grid['entry_price']:
                        self._registrar_trade(grid, row['datetime'], grid['entry_price'], grid['qty_left'], "RUNNER_BE")
                        grid['qty_left'] = 0
                        grid['status'] = 'CLOSED'

            # --- LOGICA SHORT ---
            elif grid['side'] == 'SHORT':
                # Condición 1: Tocar Banda Media
                if not grid['tp_hit'] and row['low'] <= bb_mid:
                    
                    # <--- AJUSTE CRÍTICO 2: PROTECCIÓN DE RENTABILIDAD --->
                    # Solo cerramos si la Banda Media está por DEBAJO de nuestra entrada (Ganancia)
                    if bb_mid < grid['entry_price']:
                        close_qty = self._redondear_qty(grid['qty_total'] * SimConfig.TAKE_PROFIT_PCT)
                        self._registrar_trade(grid, row['datetime'], bb_mid, close_qty, "TP_MAIN_MID")
                        
                        grid['qty_left'] -= close_qty
                        grid['tp_hit'] = True
                        grid['runner_active'] = True
                
                # Gestión del Runner
                elif grid['runner_active']:
                    if row['high'] > grid['entry_price']:
                        self._registrar_trade(grid, row['datetime'], grid['entry_price'], grid['qty_left'], "RUNNER_BE")
                        grid['qty_left'] = 0
                        grid['status'] = 'CLOSED'

    def _registrar_trade(self, grid, time, exit_price, qty, reason):
        if qty <= 0: return
        entry = grid['entry_price']
        side = grid['side']
        
        pnl = (exit_price - entry) * qty if side == 'LONG' else (entry - exit_price) * qty
        pnl_pct = (exit_price - entry) / entry if side == 'LONG' else (entry - exit_price) / entry
        
        trade_record = {
            'Grid_ID': grid['id'],
            'Side': side,
            'Entry_Date': grid['entry_time'],
            'Exit_Date': time,
            'Entry_Price': entry,
            'Exit_Price': exit_price,
            'Qty_Closed': qty,
            'PnL_USD': round(pnl, 2),
            'PnL_Pct': round(pnl_pct * 100, 2),
            'Reason': reason,
            'Is_Runner': grid['runner_active']
        }
        self.trades_history.append(trade_record)

    def generar_reporte(self):
        print("💾 Generando reporte de auditoría V2...")
        if not self.trades_history:
            print("⚠️ No se generaron operaciones.")
            return

        df_res = pd.DataFrame(self.trades_history)
        
        total_pnl = df_res['PnL_USD'].sum()
        # Filtrar trades que no sean BE (Break Even) para ver efectividad real
        trades_reales = df_res[df_res['PnL_USD'].abs() > 0.05] 
        if len(trades_reales) > 0:
            win_rate = len(trades_reales[trades_reales['PnL_USD'] > 0]) / len(trades_reales) * 100
        else:
            win_rate = 0.0
        
        print("\n" + "="*40)
        print(f"📊 RESULTADOS V2 (AGGRESSIVE + PROTECTION)")
        print("="*40)
        print(f"Total Operaciones: {len(df_res)}")
        print(f"Total PnL:         ${total_pnl:.2f}")
        print(f"Win Rate (Real):   {win_rate:.2f}%")
        print("="*40)
        
        filename = f"GridHunter_V2_AUDIT_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        path = os.path.join(reports_dir, filename)
        df_res.to_csv(path, index=False)
        print(f"✅ Reporte guardado en: {path}")

# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":
    sim = GridHunterSimulator()
    sim.cargar_datos()
    sim._ejecutar_simulacion()
    sim.generar_reporte()