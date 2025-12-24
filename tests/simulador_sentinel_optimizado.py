import pandas as pd
import numpy as np
import os
import sys
import time
from datetime import datetime

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE RUTAS
# -----------------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# Importamos Ecosistema REAL
from config.config import Config
from logic.brain import Brain
from logic.shooter import Shooter

# -----------------------------------------------------------------------------
# MOCKS (COMPONENTES VIRTUALES)
# -----------------------------------------------------------------------------
class MockLogger:
    def registrar_actividad(self, modulo, mensaje):
        pass 
    def registrar_error(self, modulo, mensaje, critico=False):
        pass
    def registrar_orden(self, paquete):
        pass

class MockFinancials:
    def __init__(self, saldo_inicial=1000.0):
        self.balance = saldo_inicial
    def get_balance_total(self):
        return self.balance
    def actualizar_balance(self, pnl):
        self.balance += pnl

class VirtualExchangeRefined:
    """
    Motor de Ejecución Refinado.
    Implementa: TRAILING STOP (1.5%) para capturar 'Money on Table' sin asfixiar el trade.
    """
    def __init__(self, financials_ref):
        self.positions = {} 
        self.closed_trades = []
        self.fin = financials_ref
        self.trade_counter = 0
        
        # Configuración de Salida
        self.TRAILING_DIST_PCT = 0.015 # 1.5% de distancia (Igual al riesgo inicial)
        self.TP_HARD_PCT = 0.05        # 5% Take Profit Fijo (Techo)

    def ejecutar_orden(self, plan, timestamp_actual, meta_info={}):
        self.trade_counter += 1
        trade_id = f"REF-{self.trade_counter}"
        
        position = {
            'id': trade_id,
            'timestamp_open': timestamp_actual,
            'strategy': plan['strategy'],
            'side': plan['side'],
            'entry_price': plan['entry_price'],
            'qty': plan['qty'],
            
            # Gestión Dinámica
            'sl_price': plan['sl_price'],     # Stop Loss Actual (Móvil)
            'hard_tp': 0.0,                   # Se calcula abajo
            'highest_price': plan['entry_price'], # Para Trailing Long
            'lowest_price': plan['entry_price'],  # Para Trailing Short
            
            # Auditoría
            'status': 'OPEN'
        }
        
        # Definir Hard TP
        if plan['side'] == 'LONG':
            position['hard_tp'] = plan['entry_price'] * (1 + self.TP_HARD_PCT)
        else:
            position['hard_tp'] = plan['entry_price'] * (1 - self.TP_HARD_PCT)
            
        self.positions[trade_id] = position
        return True

    def procesar_vela(self, candle):
        closed_ids = []
        current_low = candle['low']
        current_high = candle['high']
        ts = candle['timestamp']
        
        for pid, pos in self.positions.items():
            entry = pos['entry_price']
            side = pos['side']
            
            exit_price = 0.0
            reason = None
            
            # --- 1. ACTUALIZAR TRAILING STOP ---
            # El SL persigue al precio a una distancia de 1.5%
            
            if side == 'LONG':
                # Actualizar máximo alcanzado
                if current_high > pos['highest_price']:
                    pos['highest_price'] = current_high
                    
                    # Calcular nuevo SL potencial (Trailing)
                    new_sl = pos['highest_price'] * (1 - self.TRAILING_DIST_PCT)
                    
                    # Solo subimos el SL (nunca bajarlo)
                    if new_sl > pos['sl_price']:
                        pos['sl_price'] = new_sl
                
                # --- 2. VERIFICAR SALIDAS (LONG) ---
                # A. Stop Loss (o Trailing Hit)
                if current_low <= pos['sl_price']:
                    exit_price = pos['sl_price']
                    # Si el SL está por encima de la entrada, es ganancia asegurada (Trailing)
                    if exit_price > entry:
                        reason = 'TRAILING_STOP_WIN'
                    else:
                        reason = 'STOP_LOSS'
                
                # B. Hard Take Profit (Home Run)
                elif current_high >= pos['hard_tp']:
                    exit_price = pos['hard_tp']
                    reason = 'TAKE_PROFIT_HARD'

            else: # SHORT
                # Actualizar mínimo alcanzado
                if current_low < pos['lowest_price']:
                    pos['lowest_price'] = current_low
                    
                    # Calcular nuevo SL potencial (Price + 1.5%)
                    new_sl = pos['lowest_price'] * (1 + self.TRAILING_DIST_PCT)
                    
                    # Solo bajamos el SL (nunca subirlo en short)
                    if new_sl < pos['sl_price']:
                        pos['sl_price'] = new_sl

                # --- 2. VERIFICAR SALIDAS (SHORT) ---
                # A. Stop Loss (o Trailing Hit)
                if current_high >= pos['sl_price']:
                    exit_price = pos['sl_price']
                    if exit_price < entry: # En short, precio menor es ganancia
                        reason = 'TRAILING_STOP_WIN'
                    else:
                        reason = 'STOP_LOSS'
                
                # B. Hard Take Profit
                elif current_low <= pos['hard_tp']:
                    exit_price = pos['hard_tp']
                    reason = 'TAKE_PROFIT_HARD'

            # --- EJECUTAR SALIDA ---
            if exit_price != 0:
                self._cerrar_posicion(pos, exit_price, reason, ts)
                closed_ids.append(pid)

        for pid in closed_ids:
            del self.positions[pid]

    def _cerrar_posicion(self, pos, exit_price, reason, timestamp):
        # Calcular PnL
        if pos['side'] == 'LONG':
            pnl = (exit_price - pos['entry_price']) * pos['qty']
        else:
            pnl = (pos['entry_price'] - exit_price) * pos['qty']
        
        self.fin.actualizar_balance(pnl)
        
        log_entry = {
            'id': pos['id'],
            'fecha': datetime.fromtimestamp(pos['timestamp_open']/1000).strftime('%Y-%m-%d %H:%M'),
            'side': pos['side'],
            'entry': pos['entry_price'],
            'exit': exit_price,
            'resultado': reason,
            'pnl': round(pnl, 2)
        }
        self.closed_trades.append(log_entry)

# -----------------------------------------------------------------------------
# SIMULADOR PRINCIPAL (SIN FILTROS)
# -----------------------------------------------------------------------------
class SimuladorSentinelRefinado:
    def __init__(self):
        print("\n🦅 INICIANDO SIMULADOR REFINADO (Modo: Libre + Trailing Stop)...")
        self.cfg = Config()
        self.cfg.ENABLE_STRATEGY_GAMMA = True
        self.cfg.ENABLE_STRATEGY_SNIPER = False
        
        self.fin = MockFinancials(1000.0)
        self.logger = MockLogger()
        self.shooter = Shooter(self.cfg, self.logger, self.fin)
        self.brain = Brain(self.cfg)
        self.exchange = VirtualExchangeRefined(self.fin)
        
        self.df_15m = None

    def cargar_datos(self):
        path = os.path.join(self.cfg.DIR_DATA, f"{self.cfg.SYMBOL}_15m.csv")
        if not os.path.exists(path):
            print("❌ Error: No data found.")
            sys.exit(1)
            
        print("📂 Cargando dataset...")
        self.df_15m = pd.read_csv(path).sort_values('timestamp').reset_index(drop=True)

    def ejecutar(self):
        print("⏳ Ejecutando análisis (Puede tardar unos segundos)...")
        total_steps = len(self.df_15m)
        start_index = 200
        
        for i in range(start_index, total_steps):
            # Barra de progreso simple
            if i % 2000 == 0: print(f"   ... Procesando {i}/{total_steps}")

            row_now = self.df_15m.iloc[i]
            ts_now = row_now['timestamp']
            
            # Slicing puro para el Brain
            current_slice = self.df_15m.iloc[max(0, i-200) : i+1]
            cache = {'15m': current_slice}
            
            # 1. Procesar Mercado (Trailing Stop Check)
            self.exchange.procesar_vela(row_now)
            
            # 2. Brain (SIN FILTROS EXTERNOS, Lógica Pura)
            signal = self.brain.analizar_mercado(cache)
            
            if signal:
                # 3. Shooter (Gestión de Riesgo y Overlap)
                # Formato API para validación
                open_positions = {pid: {'side': p['side'], 'entry_price': p['entry_price'], 'qty': p['qty']} 
                                  for pid, p in self.exchange.positions.items()}
                
                plan = self.shooter.validar_y_crear_plan(signal, open_positions)
                
                if plan:
                    # Ejecutar (Exchange aplicará Trailing Stop)
                    self.exchange.ejecutar_orden(plan, ts_now)
        
        self._generar_reporte()

    def _generar_reporte(self):
        trades = self.exchange.closed_trades
        df = pd.DataFrame(trades)
        
        if df.empty:
            print("⚠️ No hubo operaciones.")
            return

        # Métricas
        wins_hard = len(df[df['resultado'] == 'TAKE_PROFIT_HARD'])
        wins_trail = len(df[df['resultado'] == 'TRAILING_STOP_WIN'])
        losses = len(df[df['resultado'] == 'STOP_LOSS'])
        total = len(df)
        
        wins_total = wins_hard + wins_trail
        pnl_neto = df['pnl'].sum()
        
        print("\n" + "="*50)
        print("📊 RESULTADOS: ESTRATEGIA REFINADA (Trailing 1.5%)")
        print("="*50)
        print(f"Operaciones Totales:    {total}")
        print(f"✅ Wins (TP Fijo 5%):    {wins_hard}")
        print(f"🛡️ Wins (Trailing):      {wins_trail} (Salvadas con ganancia)")
        print(f"❌ Losses (SL 1.5%):     {losses}")
        print("-" * 50)
        print(f"🏆 Win Rate Total:      {(wins_total/total)*100:.2f}%")
        print(f"💰 PnL Neto:            ${pnl_neto:.2f}")
        print(f"📈 Balance Final:       ${self.fin.get_balance_total():.2f}")
        print("="*50)
        
        path = os.path.join(current_dir, 'reporte_gamma_refinado.csv')
        df.to_csv(path, index=False)
        print(f"💾 Guardado: {path}")

if __name__ == "__main__":
    sim = SimuladorSentinelRefinado()
    sim.cargar_datos()
    sim.ejecutar()