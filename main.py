# =============================================================================
# UBICACIÓN: main.py
# DESCRIPCIÓN: ORQUESTADOR MAESTRO (V15.3 - INTEGRACIÓN TOTAL)
# =============================================================================

import time
import sys
import os
import pandas as pd
from datetime import datetime

<<<<<<< HEAD
# --- CONFIGURACIÓN MAESTRA ---
=======
>>>>>>> 4c4d97b (commit 24/12)
from config.config import Config

# --- LOGS & UTILIDADES ---
from logs.system_logger import SystemLogger
from connections.api_manager import APIManager
<<<<<<< HEAD

# --- EJECUCIÓN & CONTROL ---
from execution.order_manager import OrderManager
from execution.comptroller import Comptroller
from core.financials import Financials

# --- INTELIGENCIA (HÍBRIDA) ---
from logic.brain import Brain
from logic.shooter import Shooter

# --- HERRAMIENTAS DE DATOS (DATA ENGINE 2.0) ---
from tools.data_seeder import DataSeeder

# --- INTERFACES ---
=======
from execution.order_manager_1 import OrderManager
from execution.comptroller import Comptroller
from core.financials import Financials
from logic.brain import Brain
from logic.shooter import Shooter
from tools.data_seeder import DataSeeder
>>>>>>> 4c4d97b (commit 24/12)
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
<<<<<<< HEAD
        print(f"⚠️ [SUPERVISOR] Error en {modulo}: {e}")
        if self.error_count > self.max_errors:
            self.log.registrar_error("SUPERVISOR", "Límite de errores excedido. Apagado de emergencia.", critico=True)
=======
        if self.error_count > self.max_errors:
            self.log.registrar_error("SUPERVISOR", "❌ Exceso de errores críticos. Apagado de seguridad.")
>>>>>>> 4c4d97b (commit 24/12)
            sys.exit(1)

    def reportar_exito(self):
        if self.error_count > 0: self.error_count = 0

def cargar_cache_datos():
<<<<<<< HEAD
    """
    Lee del disco los DataFrames generados por el DataSeeder.
    Retorna un diccionario: {'1m': df, '5m': df, ...}
    """
    cache = {}
    # Leemos todas las temporalidades definidas en Config
=======
    """Lee cache del disco para alimentar al Cerebro."""
    cache = {}
>>>>>>> 4c4d97b (commit 24/12)
    for tf in Config.TIMEFRAMES:
        path = os.path.join(Config.DIR_DATA, f"{Config.SYMBOL}_{tf}.csv")
        if os.path.exists(path):
            try:
<<<<<<< HEAD
                # Carga optimizada
                df = pd.read_csv(path)
                cache[tf] = df
            except Exception as e:
                print(f"⚠️ Error leyendo {tf}: {e}")
    return cache

def main():
    print(f"\n🤖 INICIANDO {Config.BOT_NAME}...")
    print(f"Versión: {Config.VERSION}")
    print("=========================================")
    
    # 1. INICIALIZACIÓN DE INFRAESTRUCTURA
    Config.inicializar_infraestructura()
    log = SystemLogger()
    log.registrar_actividad("MAIN", "--- INICIANDO SISTEMA HÍBRIDO ---")
    supervisor = BotSupervisor(log)

    try:
        # 2. CONEXIONES Y FINANZAS
        print("🔌 Conectando a Binance...")
        conn = APIManager(log)
        fin = Financials(Config, conn) 
        
        # 3. GESTIÓN DE EJECUCIÓN (Contralor y OM)
        om = OrderManager(Config, conn, log)
        # El Contralor gestiona Trailing y Parciales
        comp = Comptroller(Config, om, fin, log)
        
        # 4. MOTOR DE DATOS (Data Engine 2.0)
        print("🏭 Inicializando Motor de Datos...")
        seeder = DataSeeder()
        
        # Sincronización Inicial (Descarga 1m + Resampleo Total)
        print("⏳ Sincronizando datos históricos y generando temporalidades...")
        seeder.sembrar_datos() 
        
        # Carga inicial a memoria RAM
        dfs_cache = cargar_cache_datos()
        if not dfs_cache:
            raise Exception("No se pudieron cargar datos iniciales.")
            
        print(f"✅ Datos listos. Temporalidades cargadas: {list(dfs_cache.keys())}")
        
        # 5. CEREBRO Y SHOOTER (Inteligencia Híbrida)
        brain = Brain(Config)
        shooter = Shooter(Config, log, fin)
        
        # 6. INTERFACES (Hilos paralelos)
        dash = Dashboard()
        
        # TelegramBot recibe componentes clave para reportar
        tele = TelegramBot(Config, shooter, comp, om, log, fin)
        tele.iniciar() # Hilo 1

        human = HumanInput(tele, comp, om, shooter, log)
        human.iniciar() # Hilo 2 (Input consola)

        # Sincronización inicial de posiciones con Binance
        comp.sincronizar_con_exchange()
        
        log.registrar_actividad("MAIN", "✅ SISTEMA ONLINE. Bucle de control iniciado.")
        print("🚀 SISTEMA ONLINE. Esperando cierre de vela...")
        time.sleep(1)

    except Exception as e:
        print(f"❌ Error Crítico al inicio: {e}")
        log.registrar_error("MAIN", f"Fallo en arranque: {e}", critico=True)
        sys.exit(1)

    # --- BUCLE PRINCIPAL (MAIN LOOP) ---
    
    # Variables de Control de Tiempo
    last_minute_check = 0
    cycle_counter = 0
    
    # Estado para el Dashboard
    dashboard_data = {
        'price': 0.0,
        'financials': {'balance': 0.0, 'daily_pnl': 0.0},
        'market': {'symbol': Config.SYMBOL, 'rsi': 0.0, 'volumen': 0.0, 'adx': 0.0}, # Agregado ADX
        'connections': {'binance': True, 'telegram': True},
        'positions': []
    }

=======
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
    
>>>>>>> 4c4d97b (commit 24/12)
    try:
        while True:
            now = time.time()
            
<<<<<<< HEAD
            # ============================================================
            # TAREA 1: LATIDO RÁPIDO (Cada 1 seg) - Auditoría y Precios
            # ============================================================
            try:
                # A. Precio en Tiempo Real
                current_price = conn.get_ticker_price(Config.SYMBOL)
                dashboard_data['price'] = current_price
                
                # B. Auditoría de Posiciones (Trailing Dinámico / TP Parciales)
                if current_price > 0:
                    comp.auditar_posiciones(current_price)
                
                # C. Actualizar datos financieros (menos frecuente para no saturar API)
                if cycle_counter % 5 == 0:
                    dashboard_data['financials']['balance'] = fin.get_balance_total()
                    
            except Exception as e:
                supervisor.reportar_error(e, "LOOP_FAST")

            # ============================================================
            # TAREA 2: SINCRO DE DATOS Y ANÁLISIS (Cada Minuto)
            # ============================================================
            # Verificamos si cambiamos de minuto (Reloj de vela)
            # Esto garantiza que analicemos justo después del cierre de vela
            if int(now) // 60 > last_minute_check:
                try:
                    print(f"⏱️ Nuevo minuto: Sincronizando datos... ({datetime.now().strftime('%H:%M:%S')})")
                    
                    # A. SEMBRAR DATOS (Data Engine)
                    # Descarga delta 1m -> Genera 5m, 15m, etc -> Calcula Indicadores
                    seeder.sembrar_datos()
                    
                    # B. RECARGAR CACHÉ
                    dfs_cache = cargar_cache_datos()
                    
                    # C. ACTUALIZAR DASHBOARD CON DATA TÉCNICA
                    if '15m' in dfs_cache and not dfs_cache['15m'].empty:
                        last_row = dfs_cache['15m'].iloc[-1]
                        dashboard_data['market']['rsi'] = last_row.get('rsi', 0.0)
                        dashboard_data['market']['volumen'] = last_row.get('volume', 0.0)
                        dashboard_data['market']['adx'] = last_row.get('adx', 0.0)
                    
                    # D. SINCRO CON EXCHANGE (Por si se cerró algo fuera del bot)
                    comp.sincronizar_con_exchange()
                    
                    # E. CEREBRO (Análisis Estratégico)
                    signal = brain.analizar_mercado(dfs_cache)
                    
                    if signal:
                        # F. SHOOTER (Validación y Riesgo)
                        # Pasamos la señal y las posiciones activas (para cupos)
                        plan = shooter.validar_y_crear_plan(signal, comp.posiciones_activas)
                        
                        if plan:
                            log.registrar_actividad("MAIN", f"⚡ SEÑAL CONFIRMADA: {plan['strategy']} ({plan['side']})")
                            
                            # G. ORDER MANAGER (Ejecución)
                            exito, paquete = om.ejecutar_estrategia(plan)
                            
                            if exito and paquete:
                                # H. CUSTODIA (Contralor asume el mando)
                                comp.aceptar_custodia(paquete)
                                
                                # Notificación Telegram
                                msg = (f"🚀 **ORDEN EJECUTADA**\n"
                                       f"Estrategia: {plan['strategy']}\n"
                                       f"Lado: {plan['side']}\n"
                                       f"Precio: ${plan['entry_price']:.2f}\n"
                                       f"Qty: {plan['qty']}")
                                tele.enviar_mensaje(msg)
                    
                    last_minute_check = int(now) // 60
                    supervisor.reportar_exito()
                    
                except Exception as e:
                    supervisor.reportar_error(e, "LOOP_SLOW_DATA")

            # ============================================================
            # TAREA 3: REPORTE VISUAL (Cada 3 seg)
            # ============================================================
            if cycle_counter % Config.CYCLE_DASH == 0:
                try:
                    dashboard_data['positions'] = list(comp.posiciones_activas.values())
                    dash.render(dashboard_data)
                except Exception as e:
                    pass # Dashboard no es crítico
            
            time.sleep(Config.CYCLE_FAST)
            cycle_counter += 1

    except KeyboardInterrupt:
        print("\n🛑 Apagado manual solicitado...")
        log.registrar_actividad("MAIN", "Usuario solicitó detención.")
        sys.exit(0)
    except Exception as e:
        supervisor.reportar_error(e, "CRITICAL_LOOP")
=======
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
>>>>>>> 4c4d97b (commit 24/12)
        sys.exit(1)

if __name__ == "__main__":
    main()