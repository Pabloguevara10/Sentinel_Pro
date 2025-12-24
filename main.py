# =============================================================================
# UBICACIÓN: main.py
# DESCRIPCIÓN: ORQUESTADOR MAESTRO (V15.3 - INTEGRACIÓN TOTAL)
# =============================================================================

import time
import sys
import os
import pandas as pd
from datetime import datetime

from config.config import Config
from logs.system_logger import SystemLogger
from connections.api_manager import APIManager
from execution.order_manager_1 import OrderManager
from execution.comptroller import Comptroller
from core.financials import Financials
from logic.brain import Brain
from logic.shooter import Shooter
from tools.data_seeder import DataSeeder
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
            self.log.registrar_error("SUPERVISOR", "❌ Exceso de errores críticos. Apagado de seguridad.")
            sys.exit(1)

    def reportar_exito(self):
        if self.error_count > 0: self.error_count = 0

def cargar_cache_datos():
    """Lee cache del disco para alimentar al Cerebro."""
    cache = {}
    for tf in Config.TIMEFRAMES:
        path = os.path.join(Config.DIR_DATA, f"{Config.SYMBOL}_{tf}.csv")
        if os.path.exists(path):
            try:
                # Optimización: Leer solo columnas necesarias si el archivo es muy grande
                cache[tf] = pd.read_csv(path)
            except: pass
    return cache

def main():
    # 1. INICIALIZACIÓN DE INFRAESTRUCTURA
    print(f"\n🤖 INICIANDO {Config.BOT_NAME}...")
    Config.inicializar_infraestructura()
    log = SystemLogger()
    supervisor = BotSupervisor(log)

    # Estructura de datos para el Dashboard (Estado Global)
    dashboard_data = {
        'price': 0.0,
        'financials': {'balance': 0.0, 'daily_pnl': 0.0},
        'market': {'symbol': Config.SYMBOL, 'rsi': 0.0, 'volumen': 0.0, 'adx': 0.0},
        'connections': {'binance': False, 'telegram': False},
        'positions': []
    }

    try:
        # 2. CONEXIONES Y NÚCLEO
        # Usamos 'api' para mantener consistencia de nombres
        api = APIManager(log)
        if not api.client:
            raise Exception("No se pudo conectar con Binance API.")
            
        dashboard_data['connections']['binance'] = True
        
        # Módulo Financiero
        fin = Financials(Config, api)
        
        # Ejecución
        om = OrderManager(Config, api, log)
        comp = Comptroller(om, fin)
        
        # 3. DATOS (Data Engine 2.0)
        # CORRECCIÓN: Inyectamos 'api' para no duplicar conexiones
        seeder = DataSeeder(api_manager=api)
        
        print("⏳ Sincronizando datos iniciales...")
        seeder.sembrar_datos() # Primera carga obligatoria
        dfs_cache = cargar_cache_datos()
        
        # 4. INTELIGENCIA
        brain = Brain(Config)
        shooter = Shooter(om, fin)
        
        # 5. INTERFACES
        dash = Dashboard()
        
        # Telegram Bot
        tele = TelegramBot(Config, shooter, comp, om, log, fin)
        tele.iniciar()
        if Config.TELEGRAM_TOKEN:
            dashboard_data['connections']['telegram'] = True
            
        # Human Input (Consola Táctica)
        # CORRECCIÓN CRÍTICA: Se agrega 'fin' como argumento requerido
        human = HumanInput(tele, comp, om, shooter, log, fin)
        human.iniciar()

        # Sincronización Inicial con Exchange
        comp.sincronizar_con_exchange()
        
        print("🚀 SISTEMA ONLINE. Bucle de control iniciado.")
        log.registrar_actividad("MAIN", "Sistema arrancado exitosamente.")

    except Exception as e:
        log.registrar_error("MAIN", f"Fallo fatal en arranque: {e}", critico=True)
        print(f"❌ ERROR FATAL: {e}")
        sys.exit(1)
        

    # --- BUCLE PRINCIPAL INFINITO ---
    last_minute_check = 0
    cycle_counter = 0
    
    try:
        while True:
            now = time.time()
            
            # ---------------------------------------------------------
            # TAREA 1: LATIDO RÁPIDO (Cada 1s) - Auditoría y Precios
            # ---------------------------------------------------------
            if cycle_counter % Config.CYCLE_FAST == 0:
                try:
                    # A. Precio Real (Ticker rápido)
                    try:
                        current_price = float(api.client.ticker_price(symbol=Config.SYMBOL)['price'])
                        dashboard_data['price'] = current_price
                    except: 
                        current_price = 0.0
                    
                    # B. Auditoría de Posiciones (Trailing Stops, TPs, SLs)
                    if current_price > 0:
                        comp.auditar_posiciones(current_price)
                    
                    # C. Actualizar Posiciones para el Dashboard
                    dashboard_data['positions'] = list(comp.posiciones_activas.values())

                except Exception as e:
                    supervisor.reportar_error(e, "LOOP_FAST")

            # ---------------------------------------------------------
            # TAREA 2: LÓGICA ESTRATÉGICA (Cada Ciclo Lento / Minuto)
            # ---------------------------------------------------------
            # Verificamos si pasamos a un nuevo minuto o cumplimos el ciclo lento
            is_new_minute = int(now) // 60 > last_minute_check
            
            if is_new_minute:
                try:
                    # 1. Actualizar Datos
                    dash.add_log("⏳ Analizando mercado...")
                    seeder.sembrar_datos()
                    dfs_cache = cargar_cache_datos()
                    
                    # 2. Sincronizar Estado Real (Anti-Desfase)
                    comp.sincronizar_con_exchange()
                    
                    # 3. Actualizar Datos Técnicos en Dashboard
                    if '15m' in dfs_cache and not dfs_cache['15m'].empty:
                        last_row = dfs_cache['15m'].iloc[-1]
                        dashboard_data['market']['rsi'] = last_row.get('rsi', 0.0)
                        dashboard_data['market']['adx'] = last_row.get('adx', 0.0)
                        dashboard_data['market']['volumen'] = last_row.get('volume', 0.0)
                        
                        # Actualizar Balance también en ciclo lento
                        dashboard_data['financials']['balance'] = fin.get_balance_total()

                    # 4. CEREBRO (Análisis de Señales)
                    senales = brain.analizar_mercado(dfs_cache)
                    
                    if senales:
                        for s in senales:
                            # Validar Señal con Shooter (Gestión de Riesgo y Cupos)
                            plan = shooter.validar_y_crear_plan(s, comp.posiciones_activas)
                            
                            if plan:
                                # Ejecución Blindada
                                exito, paquete = om.ejecutar_estrategia(plan)
                                if exito:
                                    comp.aceptar_custodia(paquete)
                                    msg = f"🔫 DISPARO: {plan['strategy']} {plan['side']} @ {plan['entry_price']}"
                                    tele.enviar_mensaje(msg)
                                    dash.add_log(msg)
                                else:
                                    dash.add_log(f"⛔ Fallo ejecución orden {plan['strategy']}")

                    last_minute_check = int(now) // 60
                    supervisor.reportar_exito()
                    
                except Exception as e:
                    supervisor.reportar_error(e, "LOOP_SLOW")

            # ---------------------------------------------------------
            # TAREA 3: RENDERIZADO VISUAL (Cada 3s)
            # ---------------------------------------------------------
            if cycle_counter % Config.CYCLE_DASH == 0:
                try:
                    dash.render(dashboard_data)
                except Exception:
                    pass 
            
            # Heartbeat del sistema
            time.sleep(1) 
            cycle_counter += 1

    except KeyboardInterrupt:
        log.registrar_actividad("SISTEMA", "🛑 Detención manual solicitada.")
        sys.exit(0)
    except Exception as e:
        supervisor.reportar_error(e, "CRITICAL_MAIN_LOOP")
        log.registrar_error("CRITICAL", f"Fallo fatal main loop: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()