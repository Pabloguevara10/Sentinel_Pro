import time
import sys
import os
import pandas as pd

from config.config import Config
from logs.system_logger import SystemLogger
from connections.api_manager import APIManager
from execution.order_manager import OrderManager
from execution.comptroller import Comptroller
from core.financials import Financials
from logic.brain import Brain
from logic.shooter import Shooter
from interfaces.dashboard import Dashboard
from interfaces.telegram_bot import TelegramBot
from interfaces.human_input import HumanInput

# HERRAMIENTAS DE DATOS
from tools.data_seeder import DataSeeder
from tools.fvg_scanner import FVGScanner

class BotSupervisor:
    def __init__(self, logger, max_errors=50):
        self.log = logger
        self.error_count = 0
        self.max_errors = max_errors

    def reportar_error(self, e, modulo="MAIN"):
        self.error_count += 1
        self.log.registrar_error(modulo, f"Error #{self.error_count}: {str(e)}")
        if self.error_count > self.max_errors:
            self.log.registrar_error("SUPERVISOR", "Límite de errores excedido. Apagado.", critico=True)
            sys.exit(1)

    def reportar_exito(self):
        if self.error_count > 0: self.error_count = 0

def actualizar_cache_datos(cfg):
    """Recarga los DataFrames frescos del disco a la RAM para el Cerebro."""
    cache = {}
    timeframes = ['5m', '15m', '1h'] # TFs críticos para el Brain
    for tf in timeframes:
        path = os.path.join(cfg.DIR_DATA, f"{cfg.SYMBOL}_{tf}.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                cache[tf] = df
            except: pass
    return cache

def main():
    print(f"\n🤖 INICIANDO {Config.BOT_NAME} (V11.7 - FULL REAL TIME)...")
    Config.inicializar_infraestructura()
    
    log = SystemLogger()
    log.registrar_actividad("MAIN", "--- INICIANDO SECUENCIA DE ARRANQUE ---")
    supervisor = BotSupervisor(log)

    try:
        # 1. INFRAESTRUCTURA
        conn = APIManager(log)
        fin = Financials(Config, conn) 
        om = OrderManager(Config, conn, log)
        comp = Comptroller(Config, om, fin, log)
        
        # 2. GESTIÓN DE DATOS (Arranque)
        seeder = DataSeeder()     # Sembrador (Descarga/Genera Velas)
        scanner = FVGScanner()    # Escáner (Genera Mapas)
        
        print("⏳ Sincronizando datos y mapas...")
        seeder.sembrar_datos()    # Actualiza velas 1m -> 5m, 15m...
        scanner.escanear_todo()   # Actualiza mapas FVG
        
        # Carga inicial a memoria
        dfs_cache = actualizar_cache_datos(Config)
        
        # 3. INTELIGENCIA
        brain = Brain(Config)
        shooter = Shooter(Config, log, fin)
        
        # 4. INTERFACES
        dash = Dashboard()
        tele = TelegramBot(Config, shooter, comp, om, log, fin)
        tele.iniciar()

        human = HumanInput(tele, comp, om, shooter, log)
        human.iniciar()

        log.registrar_actividad("MAIN", "✅ Sistema ONLINE.")
        print("✅ Sistema ONLINE. Entrando en bucle de control...")
        time.sleep(1)

    except Exception as e:
        print(f"❌ Error Crítico al inicio: {e}")
        log.registrar_error("MAIN", f"Fallo en arranque: {e}", critico=True)
        sys.exit(1)

    # --- BUCLE PRINCIPAL ---
    cycle_counter = 0
    market_state_cache = {'rsi_15m': 50.0, 'rsi_5m': 50.0}
    
    dashboard_data = {
        'price': 0.0,
        'financials': {'balance': 0.0, 'daily_pnl': 0.0},
        'market': {'symbol': Config.SYMBOL, 'rsi': 0.0, 'volumen': 0.0},
        'connections': {'binance': True, 'telegram': True},
        'positions': []
    }

    try:
        while True:
            # ============================================================
            # TAREA 1: LATIDO RÁPIDO (Cada 1 seg) - Precios y Gestión
            # ============================================================
            try:
                current_price = conn.get_ticker_price(Config.SYMBOL)
                dashboard_data['price'] = current_price
                
                if current_price > 0:
                    comp.auditar_posiciones(current_price, rsi_15m=market_state_cache['rsi_15m'])
                
                dashboard_data['financials']['balance'] = fin.get_balance_total()
                dashboard_data['financials']['daily_pnl'] = fin.get_daily_pnl()

            except Exception as e:
                supervisor.reportar_error(e, "LOOP_FAST")

            # ============================================================
            # TAREA 2: LÓGICA PESADA & ACTUALIZACIÓN (Cada 10 seg)
            # ============================================================
            if cycle_counter % Config.CYCLE_SLOW == 0:
                try:
                    # A. Sincronización con Binance (Posiciones reales)
                    comp.sincronizar_con_exchange()
                    
                    # B. ACTUALIZACIÓN DE DATOS (Minuto a Minuto)
                    # 1. Sembrar: Descarga 1m faltante y regenera 5m/15m en disco
                    seeder.sembrar_datos() 
                    
                    # 2. Escanear: Busca nuevos FVGs en la data fresca
                    scanner.escanear_todo()
                    
                    # 3. Recargar: Sube los datos frescos del disco a la RAM del Brain
                    dfs_cache = actualizar_cache_datos(Config)
                    
                    # C. Actualizar Datos Visuales (Dashboard)
                    if '5m' in dfs_cache and not dfs_cache['5m'].empty:
                        last_5m = dfs_cache['5m'].iloc[-1]
                        market_state_cache['rsi_5m'] = last_5m.get('rsi', 50.0)
                        dashboard_data['market']['rsi'] = market_state_cache['rsi_5m']
                        dashboard_data['market']['volumen'] = last_5m.get('volume', 0.0)
                    
                    if '15m' in dfs_cache and not dfs_cache['15m'].empty:
                        market_state_cache['rsi_15m'] = dfs_cache['15m'].iloc[-1].get('rsi', 50.0)

                    # D. ANÁLISIS ESTRATÉGICO
                    signal = brain.analizar_mercado(dfs_cache)
                    
                    if signal:
                        plan = shooter.validar_y_crear_plan(signal, comp.posiciones_activas)
                        
                        if plan:
                            log.registrar_actividad("MAIN", f"⚡ Señal {plan['strategy']} confirmada. Ejecutando...")
                            ok, paquete = om.ejecutar_estrategia(plan)
                            
                            if ok:
                                comp.aceptar_custodia(paquete)
                                msg = f"🚀 **ORDEN EJECUTADA ({plan['strategy']})**\nLado: {plan['side']}\nEntrada: ${plan['entry_price']}"
                                tele.enviar_mensaje(msg)

                except Exception as e:
                    supervisor.reportar_error(e, "LOOP_SLOW")

            # ============================================================
            # TAREA 3: REPORTE VISUAL (Cada 3 seg)
            # ============================================================
            if cycle_counter % Config.CYCLE_DASH == 0:
                try:
                    dashboard_data['positions'] = list(comp.posiciones_activas.values())
                    dash.render(dashboard_data)
                except Exception as e:
                    supervisor.reportar_error(e, "LOOP_DASH")
            
            supervisor.reportar_exito()
            time.sleep(Config.CYCLE_FAST)
            cycle_counter += 1

    except KeyboardInterrupt:
        print("\n🛑 Apagado manual solicitado...")
        log.registrar_actividad("MAIN", "Usuario solicitó detención.")
        sys.exit(0)
    except Exception as e:
        supervisor.reportar_error(e, "CRITICAL_LOOP")
        sys.exit(1)

if __name__ == "__main__":
    main()