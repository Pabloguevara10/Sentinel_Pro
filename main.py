# =============================================================================
# UBICACIÓN: main.py
# DESCRIPCIÓN: ORQUESTADOR MAESTRO (V17.8 - LECTURA DIRECTA DE DISCO)
# =============================================================================

import time
import sys
import os
import pandas as pd
from datetime import datetime

from config.config import Config

# --- LOGS & UTILIDADES ---
from logs.system_logger import SystemLogger
from connections.api_manager import APIManager
from data.historical_manager import HistoricalManager # Usado para leer disco

# --- EJECUCIÓN & CONTROL ---
from execution.order_manager import OrderManager
from execution.comptroller import Comptroller
from core.financials import Financials

# --- INTELIGENCIA ---
from logic.brain import Brain
from logic.shooter import Shooter

# --- INTERFACES ---
from interfaces.dashboard import Dashboard
from interfaces.telegram_bot import TelegramBot
from interfaces.human_input import HumanInput

class BotSupervisor:
    """Monitor de salud del sistema."""
    def __init__(self, logger, max_errors=50):
        self.log = logger
        self.error_count = 0
        self.max_errors = max_errors

    def reportar_error(self, e, modulo="MAIN"):
        self.error_count += 1
        self.log.registrar_error(modulo, f"Error #{self.error_count}: {str(e)}")
        if self.error_count > self.max_errors:
            self.log.registrar_error("SUPERVISOR", "🔥 DEMASIADOS ERRORES. APAGADO DE EMERGENCIA.")
            sys.exit(1)
            
    def reportar_exito(self):
        self.error_count = 0

def main():
    # 1. INICIALIZACIÓN DE INFRAESTRUCTURA
    Config.inicializar_infraestructura()
    logger = SystemLogger()
    supervisor = BotSupervisor(logger)
    
    logger.registrar_actividad("SYSTEM", f"🚀 Iniciando {Config.BOT_NAME} v{Config.VERSION}")
    logger.registrar_actividad("SYSTEM", f"🌍 Modo: {Config.MODE} | Par: {Config.SYMBOL}")

    try:
        # 2. CONEXIÓN Y DATOS
        api = APIManager(logger)
        fin = Financials(Config, api)
        hist_manager = HistoricalManager(api, logger) # Instancia para leer CSVs
        
        # 3. EJECUCIÓN
        om = OrderManager(Config, api, logger, fin)
        comp = Comptroller(Config, om, fin, logger)
        
        # 4. INTELIGENCIA
        shooter = Shooter(om, fin)
        brain = Brain(Config) # Brain V17.8 actualizado
        
        # 5. INTERFACES
        tele = TelegramBot(Config, shooter, comp, om, logger, fin)
        dash = Dashboard()
        cli = HumanInput(tele, comp, om, shooter, logger, fin)
        
        # Arrancar hilos secundarios
        tele.iniciar()
        cli.iniciar()
        
        # Sincronización inicial de Finanzas
        fin.sincronizar_libro_con_api()
        comp.sincronizar_con_exchange()
        
        # VARIABLES DE BUCLE
        cycle_counter = 0
        dashboard_data = {
            'price': 0.0, 'financials': {}, 'market': {}, 'connections': {}, 'positions': []
        }
        
        logger.registrar_actividad("SYSTEM", "✅ Sistema Operativo. Entrando en Bucle Principal.")

        # =====================================================================
        # BUCLE PRINCIPAL (INFINITO)
        # =====================================================================
        while True:
            # --- TAREA 1: LATIDO RÁPIDO (1s) ---
            # Actualizar precio y custodiar posiciones
            try:
                current_price = api.get_ticker_price(Config.SYMBOL)
                if current_price > 0:
                    dashboard_data['price'] = current_price
                    # El Contralor revisa trailing y parciales tick a tick
                    comp.auditar_posiciones(current_price)
            except Exception as e:
                supervisor.reportar_error(e, "TICKER")

            # --- TAREA 2: ESTRATEGIA (10s - CYCLE_SLOW) ---
            if cycle_counter % Config.CYCLE_SLOW == 0:
                try:
                    # A. Sincronizar Estado Financiero
                    fin.sincronizar_libro_con_api()
                    comp.sincronizar_con_exchange()
                    
                    # B. Cargar Datos Históricos (Desde Disco como solicitaste)
                    # Leemos los 3 DataFrames críticos para la Tríada
                    df_15m = hist_manager.obtener_dataframe_cache('15m')
                    df_1h = hist_manager.obtener_dataframe_cache('1h')
                    df_4h = hist_manager.obtener_dataframe_cache('4h')
                    
                    # Chequeo de integridad básico
                    if df_15m.empty or df_1h.empty or df_4h.empty:
                        logger.registrar_error("DATA", "⚠️ Dataframes vacíos o incompletos en disco.")
                    else:
                        # C. Análisis (Brain)
                        data_map = {'15m': df_15m, '1h': df_1h, '4h': df_4h}
                        signals = brain.analizar_mercado(data_map)
                        
                        # Actualizar Dashboard info (RSI del 15m para visual)
                        if 'rsi' in df_15m.columns:
                            dashboard_data['market']['rsi'] = df_15m.iloc[-1]['rsi']
                        
                        # D. Procesar Señales (Shooter)
                        for sig in signals:
                            # Pasamos posiciones activas para validar cupos
                            plan = shooter.validar_y_crear_plan(sig, comp.posiciones_activas)
                            
                            if plan:
                                logger.registrar_actividad("MAIN", f"⚡ SEÑAL: {plan['strategy']} ({plan['side']})")
                                exito, paquete = om.ejecutar_estrategia(plan)
                                
                                if exito and paquete:
                                    comp.aceptar_custodia(paquete)
                                    tele.enviar_mensaje(f"🚀 ORDEN EJECUTADA: {plan['strategy']} @ {paquete['entry_price']}")
                    
                    supervisor.reportar_exito()
                    
                except Exception as e:
                    supervisor.reportar_error(e, "LOOP_STRATEGY")

            # --- TAREA 3: VISUAL (3s) ---
            if cycle_counter % Config.CYCLE_DASH == 0:
                try:
                    dashboard_data['financials']['balance'] = fin.get_balance_total()
                    dashboard_data['connections']['binance'] = (dashboard_data['price'] > 0)
                    dashboard_data['connections']['telegram'] = tele.running
                    dashboard_data['positions'] = list(comp.posiciones_activas.values())
                    dash.render(dashboard_data)
                except Exception: pass
            
            time.sleep(Config.CYCLE_FAST)
            cycle_counter += 1

    except KeyboardInterrupt:
        print("\n🛑 Apagado manual solicitado...")
        sys.exit(0)
    except Exception as e:
        supervisor.reportar_error(e, "CRITICAL_LOOP")

if __name__ == "__main__":
    main()