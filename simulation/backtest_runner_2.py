# =============================================================================
# UBICACIÓN: simulation/backtest_runner.py
# DESCRIPCIÓN: ORQUESTADOR V4 (PRE-CALCULO + OPTIMIZADO + 1M)
# =============================================================================

import sys
import os
import pandas as pd
import time
from datetime import datetime, timedelta

# --- 1. CONFIG PATH Y HACK VELOCIDAD ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

import execution.order_manager
# Neutralizamos el time.sleep para que vuele
execution.order_manager.time.sleep = lambda t: None 

from config.config import Config
from execution.order_manager import OrderManager
from execution.comptroller import Comptroller
from core.financials import Financials
from logic.brain import Brain
from logic.shooter import Shooter
from tools.precision_lab import PrecisionLab 
from simulation.mock_api import MockAPIManager

class DummyLogger:
    def __init__(self): pass
    def registrar_actividad(self, modulo, msg): pass
    def registrar_error(self, modulo, msg, critico=False):
        print(f"❌ [ERROR] {modulo}: {msg}")

def cargar_y_procesar_data():
    """Carga data y PRE-CALCULA indicadores para eficiencia máxima."""
    cache = {}
    lab = PrecisionLab()
    
    files = {
        '1m':  f"{Config.SYMBOL}_1m.csv",
        '15m': f"{Config.SYMBOL}_15m.csv",
        '1h':  f"{Config.SYMBOL}_1h.csv",
        '4h':  f"{Config.SYMBOL}_4h.csv"
    }
    
    print("⏳ Cargando datos y calculando indicadores globales (Pre-Process)...")
    
    for tf, filename in files.items():
        path = os.path.join(Config.DIR_DATA, filename)
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                if 'timestamp' in df.columns:
                    if df.iloc[0]['timestamp'] > 20000000000: 
                        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                    else:
                        df['datetime'] = pd.to_datetime(df['timestamp'])
                    df.set_index('datetime', inplace=True)
                    df.sort_index(inplace=True)
                
                # --- OPTIMIZACIÓN: CÁLCULO UNICO ---
                # Calculamos RSI, BB, ATR una sola vez para todo el histórico.
                if tf in ['15m', '1h', '4h']:
                    df = lab.calcular_indicadores_full(df)
                    print(f"   ✨ Indicadores listos para {tf}")

                cache[tf] = df
                print(f"   ✅ {tf}: {len(df)} velas.")
            except Exception as e:
                print(f"   ⚠️ Error procesando {filename}: {e}")
        else:
            if tf == '1m': print(f"   ⚠️ NO SE ENCONTRÓ DATA 1M (Se usará modo rápido 15m).")
            else: print(f"   ❌ ERROR FATAL: Falta {tf}"); sys.exit(1)
            
    return cache

def main():
    print("\n🏎️ BACKTEST V4 (RAM OPTIMIZADA + SHADOW FIX)")
    print("===========================================")
    
    log = DummyLogger()
    mock_api = MockAPIManager(log, initial_balance=1000.0)
    
    fin = Financials(Config, mock_api)
    om = OrderManager(Config, mock_api, log, financials=fin)
    comp = Comptroller(Config, om, fin, log)
    brain = Brain(Config)
    shooter = Shooter(om, fin)
    
    # Carga optimizada
    full_cache = cargar_y_procesar_data()
    df_15m = full_cache['15m']
    df_1m = full_cache.get('1m', pd.DataFrame())
    has_1m = not df_1m.empty
    
    print(f"🚀 Iniciando simulación sobre {len(df_15m)} velas de 15m...")
    start_sim = time.time()
    
    # Empezamos en vela 50 (ya tenemos indicadores, no necesitamos esperar 200)
    for i in range(50, len(df_15m)):
        current_candle = df_15m.iloc[i]
        current_ts = current_candle.name
        
        # --- FASE 1: MICRO-SIMULACIÓN (1M) ---
        if has_1m:
            next_ts = current_ts + timedelta(minutes=15)
            # Slicing rápido
            micro_candles = df_1m.truncate(before=current_ts, after=next_ts - timedelta(seconds=1))
            
            for idx_1m, candle_1m in micro_candles.iterrows():
                mock_api.update_market_state(candle_1m['close'], idx_1m)
                mock_api.check_fills(candle_1m['high'], candle_1m['low'])
                comp.auditar_posiciones(candle_1m['close'])
        else:
            mock_api.update_market_state(current_candle['close'], current_ts)
            mock_api.check_fills(current_candle['high'], current_candle['low'])
            comp.auditar_posiciones(current_candle['close'])

        # --- FASE 2: CEREBRO ---
        # Enviamos el slice, PERO ya tiene los indicadores. El Brain será rápido.
        sliced_cache = {}
        sliced_cache['15m'] = df_15m.iloc[:i+1]
        
        # Sync TFs mayores (menos frecuente para ahorrar CPU)
        if i % 4 == 0: 
             if '1h' in full_cache: sliced_cache['1h'] = full_cache['1h'][:current_ts]
             if '4h' in full_cache: sliced_cache['4h'] = full_cache['4h'][:current_ts]

        signals = brain.analizar_mercado(sliced_cache)
        
        if signals:
            lista_senales = signals if isinstance(signals, list) else [signals]
            for sig in lista_senales:
                plan = shooter.validar_y_crear_plan(sig, comp.posiciones_activas)
                if plan:
                    plan['timestamp'] = str(current_ts)
                    # Ahora las órdenes LIMIT de Shadow se llenarán si son válidas
                    exito, paquete = om.ejecutar_estrategia(plan)
                    if exito and paquete:
                        comp.aceptar_custodia(paquete)
                        print(f"   ⚡ [{current_ts}] {plan['strategy']} ({plan['side']}) @ {plan['entry_price']}")

        # LOG VISUAL (Cada 500 velas para no saturar consola)
        if i % 500 == 0:
            elapsed = time.time() - start_sim
            print(f"   📅 {current_ts} | Bal: {mock_api.balance_usdt:.0f} | Pos: {len(comp.posiciones_activas)} | T: {elapsed:.1f}s")

    print("\n🏁 FIN. Resultados guardados en 'simulation_report_v17.csv'")
    print(f"💰 Balance Final: ${mock_api.balance_usdt:.2f}")

if __name__ == "__main__":
    main()