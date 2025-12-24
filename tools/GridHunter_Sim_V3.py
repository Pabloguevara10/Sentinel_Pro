# =============================================================================
# NOMBRE: GridHunter_Sim_V3.py (Diagnostic & Circuit Breaker)
# DESCRIPCIÓN: 
#   Simulador V3 para 'Stress Test' con Diagnóstico Avanzado.
#   - NUEVO: Circuit Breaker (Límite de Grids Activos).
#   - NUEVO: Reporte Extendido (RSI, ADX, BBW, MAE, Holding Time).
#   - Permite detectar "Rangos de Estrés" (Mucho capital, poco retorno).
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

# --- CLASE DE CONFIGURACIÓN ---
class SimConfig:
    SYMBOL = "AAVEUSDT"
    QTY_PRECISION = 1     
    PRICE_PRECISION = 2   
    MIN_QTY = 0.1
    
    # Archivo de 1 Año
    FILE_15M = os.path.join(data_dir, "AAVEUSDT_15m.csv")
    
    # --- PARÁMETROS ESTRATEGIA (V2.1) ---
    BB_PERIOD = 20
    BB_STD_DEV = 1.8         # Agresivo
    
    # Gestión de Entradas
    GRID_LEVELS = 5          
    GRID_STEP_ATR_MULT = 0.5 
    
    # --- CIRCUIT BREAKER (NUEVO) ---
    # Límite de seguridad: Si hay 10 grids abiertos (Aprox $1000 riesgo), no abre más.
    # Esto evita el "sobre-apalancamiento" en tendencias infinitas.
    MAX_ACTIVE_GRIDS = 10    
    
    # Gestión de Salidas
    TAKE_PROFIT_PCT = 0.60   
    RUNNER_PCT = 0.40        
    
    # Lotes (Asimetría)
    BASE_RISK_USD = 100.0    
    TREND_BIAS_RATIO = 1.0   
    COUNTER_BIAS_RATIO = 0.6 

# --- HERRAMIENTAS ---
class MockPrecisionLab:
    @staticmethod
    def calcular_bollinger(df, period=20, std_dev=2.0):
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        # Ancho de banda (Volatilidad relativa)
        bb_width = (upper - lower) / sma
        return upper, sma, lower, bb_width

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

# --- MOTOR SIMULADOR V3 ---
class GridHunterSimulatorV3:
    def __init__(self):
        self.trades_history = []
        self.active_grids = [] 
        self.lab = MockPrecisionLab()
        self.peak_active_grids = 0 # Metrica de diagnóstico
        print(f"🤖 INICIANDO GRIDHUNTER V3 (DIAGNOSTIC MODE)")

    def cargar_datos(self):
        print("⏳ Cargando datos históricos...")
        try:
            self.df = pd.read_csv(SimConfig.FILE_15M)
            self.df['datetime'] = pd.to_datetime(self.df['timestamp'], unit='ms')
            
            # Recalcular BB con parámetros de Config
            # Nota: Si el CSV ya tiene RSI/ADX usaremos esos directamente.
            self.df['bb_upper'], self.df['bb_mid'], self.df['bb_lower'], self.df['bb_width'] = \
                self.lab.calcular_bollinger(self.df, SimConfig.BB_PERIOD, SimConfig.BB_STD_DEV)
            
            # Asegurar ATR
            if 'atr' not in self.df.columns or self.df['atr'].isnull().all():
                self.df['atr'] = self.lab.calcular_atr(self.df)
            
            self.df.dropna(inplace=True)
            self.df.reset_index(drop=True, inplace=True)
            print(f"✅ Datos listos: {len(self.df)} velas.")
            
        except FileNotFoundError:
            print("❌ Error: No se encuentra AAVEUSDT_15m.csv")
            sys.exit(1)

    def _redondear_qty(self, qty):
        fmt = "{:." + str(SimConfig.QTY_PRECISION) + "f}"
        return float(fmt.format(qty))

    def _ejecutar_simulacion(self):
        print("🚀 Ejecutando Stress Test con Diagnóstico (Esto puede tardar)...")
        
        trend_direction = 'NEUTRAL' 
        
        for i, row in self.df.iterrows():
            current_price = row['close']
            
            # Actualizar métrica de carga del sistema (Cuántos grids hay abiertos)
            current_load = len([g for g in self.active_grids if g['status'] == 'OPEN'])
            if current_load > self.peak_active_grids:
                self.peak_active_grids = current_load
            
            # 1. GESTIONAR POSICIONES
            self._gestionar_posiciones(row, current_load)
            
            # 2. DEFINIR TENDENCIA
            if current_price > row['bb_mid']: trend_direction = 'BULLISH'
            else: trend_direction = 'BEARISH'
            
            # 3. BUSCAR ENTRADAS (Con Circuit Breaker)
            # Solo buscamos entrada si no hemos superado el límite de carga
            if current_load < SimConfig.MAX_ACTIVE_GRIDS:
                self._buscar_entradas(row, trend_direction, current_load)

    def _buscar_entradas(self, row, trend, current_load):
        price = row['close']
        upper = row['bb_upper']
        lower = row['bb_lower']
        atr = row['atr']
        
        # --- LOGICA SHORT ---
        if row['high'] >= upper:
            if not self._existe_orden_cercana('SHORT', price, atr):
                qty_calc = (SimConfig.BASE_RISK_USD / price)
                if trend == 'BEARISH': qty_calc *= SimConfig.TREND_BIAS_RATIO
                else: qty_calc *= SimConfig.COUNTER_BIAS_RATIO
                
                self._abrir_orden('SHORT', price, qty_calc, row, "BB_TOUCH_UPPER", current_load)

        # --- LOGICA LONG ---
        if row['low'] <= lower:
            if not self._existe_orden_cercana('LONG', price, atr):
                qty_calc = (SimConfig.BASE_RISK_USD / price)
                if trend == 'BULLISH': qty_calc *= SimConfig.TREND_BIAS_RATIO
                else: qty_calc *= SimConfig.COUNTER_BIAS_RATIO
                
                self._abrir_orden('LONG', price, qty_calc, row, "BB_TOUCH_LOWER", current_load)

    def _existe_orden_cercana(self, side, price, atr):
        min_dist = atr * SimConfig.GRID_STEP_ATR_MULT
        for grid in self.active_grids:
            if grid['side'] == side and grid['status'] == 'OPEN':
                if abs(grid['entry_price'] - price) < min_dist:
                    return True
        return False

    def _abrir_orden(self, side, price, qty, row, reason, system_load):
        qty = self._redondear_qty(qty)
        if qty < SimConfig.MIN_QTY: return
        
        grid_id = f"G_{int(row['timestamp']/1000)}"
        
        # Captura de Indicadores al momento de ENTRADA (Snapshot Diagnóstico)
        # Usamos los del CSV si existen, si no, valores neutros
        rsi = row['rsi'] if 'rsi' in row else 50
        adx = row['adx'] if 'adx' in row else 25
        bbw = row.get('bb_width', 0)
        
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
            'max_price': price, # Para cálculo MAE
            'min_price': price, # Para cálculo MAE
            
            # --- DATOS DIAGNÓSTICO ---
            'entry_rsi': rsi,
            'entry_adx': adx,
            'entry_bbw': bbw,
            'system_load_at_entry': system_load
        }
        self.active_grids.append(order)

    def _gestionar_posiciones(self, row, current_system_load):
        bb_mid = row['bb_mid']
        
        for grid in self.active_grids:
            if grid['status'] != 'OPEN': continue
            
            # Actualizar Drawdown (MAE)
            if row['high'] > grid['max_price']: grid['max_price'] = row['high']
            if row['low'] < grid['min_price']: grid['min_price'] = row['low']
            
            # --- LOGICA LONG ---
            if grid['side'] == 'LONG':
                if not grid['tp_hit'] and row['high'] >= bb_mid:
                    # Profit Protection: Solo cerrar si ganamos
                    if bb_mid > grid['entry_price']:
                        close_qty = self._redondear_qty(grid['qty_total'] * SimConfig.TAKE_PROFIT_PCT)
                        self._registrar_trade(grid, row, bb_mid, close_qty, "TP_MAIN_MID", current_system_load)
                        grid['qty_left'] -= close_qty
                        grid['tp_hit'] = True
                        grid['runner_active'] = True 
                
                elif grid['runner_active']:
                    if row['low'] < grid['entry_price']:
                        self._registrar_trade(grid, row, grid['entry_price'], grid['qty_left'], "RUNNER_BE", current_system_load)
                        grid['qty_left'] = 0
                        grid['status'] = 'CLOSED'

            # --- LOGICA SHORT ---
            elif grid['side'] == 'SHORT':
                if not grid['tp_hit'] and row['low'] <= bb_mid:
                    # Profit Protection
                    if bb_mid < grid['entry_price']:
                        close_qty = self._redondear_qty(grid['qty_total'] * SimConfig.TAKE_PROFIT_PCT)
                        self._registrar_trade(grid, row, bb_mid, close_qty, "TP_MAIN_MID", current_system_load)
                        grid['qty_left'] -= close_qty
                        grid['tp_hit'] = True
                        grid['runner_active'] = True
                
                elif grid['runner_active']:
                    if row['high'] > grid['entry_price']:
                        self._registrar_trade(grid, row, grid['entry_price'], grid['qty_left'], "RUNNER_BE", current_system_load)
                        grid['qty_left'] = 0
                        grid['status'] = 'CLOSED'

    def _registrar_trade(self, grid, row, exit_price, qty, reason, system_load):
        if qty <= 0: return
        entry = grid['entry_price']
        side = grid['side']
        exit_time = row['datetime']
        
        pnl = (exit_price - entry) * qty if side == 'LONG' else (entry - exit_price) * qty
        pnl_pct = (exit_price - entry) / entry if side == 'LONG' else (entry - exit_price) / entry
        
        # Calcular MAE (Max Adverse Excursion) %
        # Cuánto se fue en contra antes de cerrar (Medida de estrés)
        if side == 'LONG':
            mae_price = grid['min_price']
            mae_pct = (mae_price - entry) / entry # Será negativo
        else:
            mae_price = grid['max_price']
            mae_pct = (entry - mae_price) / entry # Será negativo
            
        # Holding Time (Minutos)
        duration = (exit_time - grid['entry_time']).total_seconds() / 60
        
        trade_record = {
            'Grid_ID': grid['id'],
            'Side': side,
            'Entry_Date': grid['entry_time'],
            'Exit_Date': exit_time,
            'Entry_Price': entry,
            'Exit_Price': exit_price,
            'Qty_Closed': qty,
            'PnL_USD': round(pnl, 2),
            'PnL_Pct': round(pnl_pct * 100, 2),
            'Reason': reason,
            
            # --- CAMPOS DE DIAGNÓSTICO ---
            'Entry_RSI': round(grid['entry_rsi'], 2),
            'Entry_ADX': round(grid['entry_adx'], 2),
            'Entry_BBW': round(grid['entry_bbw'], 4),
            'System_Load_Entry': grid['system_load_at_entry'],
            'System_Load_Exit': system_load,
            'MAE_Pct': round(mae_pct * 100, 2), # Drawdown individual de la operación
            'Duration_Min': int(duration)
        }
        self.trades_history.append(trade_record)

    def generar_reporte(self):
        print("💾 Generando Reporte Diagnóstico V3...")
        if not self.trades_history:
            print("⚠️ No se generaron operaciones.")
            return

        df_res = pd.DataFrame(self.trades_history)
        
        total_pnl = df_res['PnL_USD'].sum()
        trades_reales = df_res[df_res['PnL_USD'].abs() > 0.05] 
        win_rate = (len(trades_reales[trades_reales['PnL_USD'] > 0]) / len(trades_reales) * 100) if len(trades_reales) > 0 else 0
        
        print("\n" + "="*40)
        print(f"📊 DIAGNÓSTICO GRIDHUNTER V3 (CB={SimConfig.MAX_ACTIVE_GRIDS})")
        print("="*40)
        print(f"Total Operaciones: {len(df_res)}")
        print(f"Total PnL:         ${total_pnl:.2f}")
        print(f"Win Rate (Real):   {win_rate:.2f}%")
        print(f"Peak Active Grids: {self.peak_active_grids}")
        print("="*40)
        
        filename = f"GridHunter_V3_DIAGNOSTIC_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        path = os.path.join(reports_dir, filename)
        df_res.to_csv(path, index=False)
        print(f"✅ Reporte Extendido guardado en: {path}")

# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":
    sim = GridHunterSimulatorV3()
    sim.cargar_datos()
    sim._ejecutar_simulacion()
    sim.generar_reporte()