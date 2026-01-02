# =============================================================================
# UBICACIÓN: simulation/backtest_runner.py
# DESCRIPCIÓN: ORQUESTADOR V10 (TURBO SILENCIOSO + ESTADÍSTICAS)
# =============================================================================

import sys
import os
import pandas as pd
import time
from datetime import datetime, timedelta

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

import execution.order_manager
# Hack de velocidad: anulamos el sleep
execution.order_manager.time.sleep = lambda t: None 

from config.config import Config
from execution.order_manager import OrderManager
from execution.comptroller import Comptroller
from core.financials import Financials
from logic.brain import Brain
from logic.shooter import Shooter
from simulation.mock_api import MockAPIManager

# --- FILTRO HOME RUN (OPTIMIZADO) ---
def check_home_run_conditions(df_15m, df_5m):
    """
    Retorna True/False. Eliminamos el string de razón para ganar velocidad.
    """
    try:
        if len(df_15m) < 5 or len(df_5m) < 6: return False

        # Acceso directo por posición (más rápido que iloc con nombres si es posible, pero iloc es seguro)
        # Usamos .iat si es posible para velocidad extrema, pero .iloc está bien para 80k velas
        
        # 15m
        adx_15 = df_15m.iloc[-1]['ADX']
        # rsi_15 = df_15m.iloc[-1]['RSI']
        # rsi_15_prev = df_15m.iloc[-4]['RSI'] # T-3
        
        # Micro-optimizacion: Si ADX es bajo, rechazar ya.
        if adx_15 < 20: return False

        # Pullback 15m: RSI debe estar bajando (o plano) respecto a hace 3 velas
        if df_15m.iloc[-1]['RSI'] >= df_15m.iloc[-4]['RSI']: return False

        # 5m
        # Rebote 5m: RSI debe estar subiendo respecto a hace 5 velas
        # Suavizado: Exigimos +0.5 en lugar de +1.0 para ser menos restrictivos
        if df_5m.iloc[-1]['RSI'] <= (df_5m.iloc[-6]['RSI'] + 0.5): return False

        return True

    except:
        return True # Fail-open en error de datos

class DummyLogger:
    def __init__(self): pass
    def registrar_actividad(self, modulo, msg): pass
    def registrar_error(self, modulo, msg, critico=False): pass # Silencio total en errores no críticos

def cargar_y_procesar_data():
    try:
        from simulation.data_loader import cargar_y_procesar_data as loader
        return loader()
    except ImportError:
        return None

def main():
    print("🚀 INICIANDO BACKTEST: MODO TURBO (SILENCIOSO)")
    print("ℹ️  Los rechazos NO se imprimirán para maximizar velocidad.")
    
    logger = DummyLogger()
    
    # SETUP
    mock_api = MockAPIManager(logger, initial_balance=10000.0, stress_mode=True)
    fin = Financials(Config, mock_api)
    om = OrderManager(Config, mock_api, logger, fin)
    comp = Comptroller(Config, om, fin, logger)
    brain = Brain(Config)
    shooter = Shooter(om, fin)
    
    # CARGA DATOS
    full_cache = cargar_y_procesar_data()
    if not full_cache: return

    df_1m = full_cache['1m']
    timestamps = df_1m.index
    total_candles = len(timestamps)
    
    sliced_cache = {tf: df.iloc[:0] for tf, df in full_cache.items()}
    
    print(f"📊 Velas a procesar: {total_candles}")
    
    start_time = time.time()
    signals_detected = 0
    signals_accepted = 0

    # LOOP PRINCIPAL
    for i, current_ts in enumerate(timestamps):
        if i < 300: continue 
        
        # Actualizar precio
        current_close = df_1m.iloc[i]['close'] 
        mock_api.update_market_price(current_close, str(current_ts))

        # Slicing (Optimizado: solo actualizamos punteros cada 5 min)
        if i % 5 == 0: 
            if '15m' in full_cache: sliced_cache['15m'] = full_cache['15m'].loc[:current_ts]
            if '5m' in full_cache: sliced_cache['5m'] = full_cache['5m'].loc[:current_ts]
        sliced_cache['1m'] = full_cache['1m'].loc[:current_ts]
        
        # LÓGICA (Solo si Brain detecta algo, corremos el filtro pesado)
        signals = brain.analizar_mercado(sliced_cache)
        
        if signals:
            lista_senales = signals if isinstance(signals, list) else [signals]
            
            for sig in lista_senales:
                signals_detected += 1
                
                # FILTRO SILENCIOSO
                if '15m' in sliced_cache and '5m' in sliced_cache:
                    if not check_home_run_conditions(sliced_cache['15m'], sliced_cache['5m']):
                        continue # Rechazo silencioso

                plan = shooter.validar_y_crear_plan(sig, comp.posiciones_activas)
                
                if plan:
                    # Stress Test SL
                    entry = plan['entry_price']
                    if plan['side'] == 'LONG':
                        sl_audit = entry * 0.978 
                        plan['stop_loss'] = max(plan.get('stop_loss', 0), sl_audit)
                    else:
                        sl_audit = entry * 1.022
                        plan['stop_loss'] = min(plan.get('stop_loss', 999999), sl_audit)

                    plan['timestamp'] = str(current_ts)
                    
                    exito, paquete = om.ejecutar_estrategia(plan)
                    if exito and paquete:
                        signals_accepted += 1
                        comp.aceptar_custodia(paquete)
                        print(f"💎 [{current_ts}] ENTRY {plan['side']} @ {entry}")

        # LOG VISUAL (Solo cada 2000 velas para velocidad)
        if i % 2000 == 0:
            progreso = (i / total_candles) * 100
            elapsed = time.time() - start_time
            velocidad = i / elapsed if elapsed > 0 else 0
            print(f"   📅 {current_ts} ({progreso:.1f}%) | Bal: {mock_api.balance_usdt:.0f} | Ops: {signals_accepted}/{signals_detected} | {velocidad:.0f} velas/s")

    print(f"\n🏁 FIN. Balance Final: ${mock_api.balance_usdt:.2f}")
    print(f"📈 Total Señales: {signals_detected} | Aceptadas por Filtro: {signals_accepted}")

if __name__ == "__main__":
    main()