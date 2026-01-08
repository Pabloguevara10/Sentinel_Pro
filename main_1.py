# =============================================================================
# UBICACIÓN: main.py
# DESCRIPCIÓN: ORQUESTADOR MAESTRO (V19.0 - CON TELEGRAM INTENT REPORT)
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
from data.historical_manager import HistoricalManager 

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
    """Monitor de salud del sistema con tolerancia a fallos de red."""
    def __init__(self, logger, max_errors=50):
        self.log = logger
        self.error_count = 0
        self.max_errors = max_errors
        self.en_pausa_red = False

    def reportar_error_conexion(self, e):
        """Maneja errores de red sin apagar el bot."""
        if not self.en_pausa_red:
            self.log.registrar_error("RED", f"⚠️ Conexión Perdida: {e}. Entrando en modo RECONEXIÓN...")
            self.en_pausa_red = True
        else:
            print(".", end="", flush=True)

    def reportar_recuperacion(self):
        """Se llama cuando una operación de red tiene éxito tras un fallo."""
        if self.en_pausa_red:
            print("\n") 
            self.log.registrar_actividad("RED", "✅ CONEXIÓN RESTABLECIDA. Reanudando operaciones.")
            self.en_pausa_red = False
            self.error_count = 0 

    def reportar_error_critico(self, e, modulo="MAIN"):
        """Errores de lógica que sí suman al contador de apagado."""
        self.error_count += 1
        self.log.registrar_error(modulo, f"Error Crítico #{self.error_count}: {str(e)}")
        if self.error_count > self.max_errors:
            self.log.registrar_error("SUPERVISOR", "🔥 DEMASIADOS ERRORES CRÍTICOS. APAGADO DE EMERGENCIA.")
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
        hist_manager = HistoricalManager(api, logger) 
        
        # Sincronización Inicial de Datos
        logger.registrar_actividad("MAIN", "⏳ Sincronizando datos históricos iniciales...")
        hist_manager.sincronizar_infraestructura_datos()
        
        # 3. EJECUCIÓN
        om = OrderManager(Config, api, logger, fin)
        comp = Comptroller(Config, om, fin, logger)
        
        # 4. INTELIGENCIA
        shooter = Shooter(om, fin)
        brain = Brain(Config) 
        
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
        
        # --- RECUPERACIÓN DE ESTADO (AUTO-RECOVERY) ---
        logger.registrar_actividad("MAIN", "🔎 Buscando posiciones huérfanas en Binance para adoptar...")
        comp.adoptar_posiciones_huerfanas()
        
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
            try:
                # Verificación de conexión
                current_price = api.get_ticker_price(Config.SYMBOL)
                if current_price == 0: raise Exception("API Price Zero")
                
                supervisor.reportar_recuperacion()
                
                dashboard_data['price'] = current_price
                comp.auditar_posiciones(current_price)
                
            except Exception as e:
                supervisor.reportar_error_conexion(e)
                time.sleep(5) 
                continue 

            # --- TAREA 2: ESTRATEGIA (10s - CYCLE_SLOW) ---
            if cycle_counter % Config.CYCLE_SLOW == 0:
                try:
                    # A. Sincronizar
                    fin.sincronizar_libro_con_api()
                    comp.sincronizar_con_exchange()
                    
                    # B. Datos
                    hist_manager.sincronizar_infraestructura_datos()
                    df_15m = hist_manager.obtener_dataframe_cache('15m')
                    df_1h = hist_manager.obtener_dataframe_cache('1h')
                    df_4h = hist_manager.obtener_dataframe_cache('4h')
                    
                    if df_15m.empty or df_1h.empty or df_4h.empty:
                        logger.registrar_error("DATA", "⚠️ Dataframes vacíos o incompletos en disco.")
                    else:
                        # C. Análisis
                        data_map = {'15m': df_15m, '1h': df_1h, '4h': df_4h}
                        signals = brain.analizar_mercado(data_map)
                        
                        if 'rsi' in df_15m.columns:
                            dashboard_data['market']['rsi'] = df_15m.iloc[-1]['rsi']
                        
                        # D. Ejecución
                        for sig in signals:
                            plan = shooter.validar_y_crear_plan(sig, comp.posiciones_activas)
                            
                            if plan:
                                logger.registrar_actividad("MAIN", f"⚡ SEÑAL APROBADA: {plan['strategy']} ({plan['side']})")
                                
                                # --- NUEVO: REPORTE DE INTENCIÓN A TELEGRAM ---
                                tele.reportar_intencion_entrada(plan)
                                
                                # Ejecución
                                exito, paquete = om.ejecutar_estrategia(plan)
                                
                                if exito and paquete:
                                    comp.aceptar_custodia(paquete)
                                    msg = f"🚀 ORDEN CONFIRMADA: {plan['strategy']} @ {paquete['entry_price']}"
                                    tele.enviar_mensaje(msg)
                                    logger.registrar_actividad("MAIN", msg)
                    
                    supervisor.reportar_exito()
                    
                except Exception as e:
                    supervisor.reportar_error_critico(e, "LOOP_STRATEGY")

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
        supervisor.reportar_error_critico(e, "CRITICAL_LOOP")

if __name__ == "__main__":
    main()