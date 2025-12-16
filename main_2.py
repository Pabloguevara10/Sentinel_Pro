import time
import sys
import os

# --- 1. IMPORTACIÓN DE DEPARTAMENTOS (Infraestructura) ---
from config.config import Config
from logs.system_logger import SystemLogger
from connections.api_manager import APIManager

# --- 2. IMPORTACIÓN DE OPERATIVA (Músculo) ---
from execution.order_manager import OrderManager
from execution.comptroller import Comptroller
from core.financials import Financials

# --- 3. IMPORTACIÓN DE ESTRATEGIA (Cerebro) ---
from logic.brain import Brain
from logic.shooter import Shooter
from data.historical_manager import HistoricalDataManager

# --- 4. IMPORTACIÓN DE INTERFACES (Rostro) ---
from interfaces.dashboard import Dashboard
from interfaces.telegram_bot import TelegramBot
from interfaces.human_input import HumanInput

class BotSupervisor:
    """
    SUPERVISOR INTERNO: Vigila la salud del proceso principal.
    Si ocurren demasiados errores consecutivos, detiene el bot por seguridad.
    """
    def __init__(self, logger, max_errors=50):
        self.log = logger
        self.error_count = 0
        self.max_errors = max_errors

    def reportar_error(self, e, modulo="MAIN"):
        self.error_count += 1
        self.log.registrar_error(modulo, f"Error #{self.error_count}: {str(e)}")
        # No imprimimos en consola para no ensuciar el Dashboard, solo al log
        
        if self.error_count > self.max_errors:
            self.log.registrar_error("SUPERVISOR", "Límite de errores excedido. Apagado de emergencia.", critico=True)
            sys.exit(1)

    def reportar_exito(self):
        # Si un ciclo se completa bien, reseteamos el contador
        if self.error_count > 0:
            self.error_count = 0

def main():
    # --- A. ARRANQUE DE INFRAESTRUCTURA ---
    print(f"\n🤖 INICIANDO {Config.BOT_NAME}...")
    Config.inicializar_infraestructura()
    
    log = SystemLogger()
    log.registrar_actividad("MAIN", "--- SISTEMA INICIANDO SECUENCIA DE ARRANQUE ---")

    supervisor = BotSupervisor(log)

    try:
        # --- B. CONEXIÓN Y DEPARTAMENTOS ---
        # 1. Conexión (API)
        conn = APIManager(log)
        
        # 2. Finanzas (Wallet & PnL)
        # Se encarga de calcular saldo real y ganancias del día
        fin = Financials(Config, conn) 
        
        # 3. Operaciones (Ejecución y Control)
        om = OrderManager(Config, conn, log)
        comp = Comptroller(Config, om, fin, log)
        
        # 4. Datos y Estrategia (Cerebro)
        data_manager = HistoricalDataManager(Config, conn, log)
        print("⏳ Minando y sincronizando datos históricos (puede tardar un poco)...")
        dfs_cache = data_manager.inicializar_datos()
        
        brain = Brain(Config)
        shooter = Shooter(Config, log)
        
        # 5. Interfaces de Usuario
        dash = Dashboard()

        # >> HILO 1: Telegram Bot
        tele = TelegramBot(Config, shooter, comp, om, log, fin)
        tele.iniciar()

        # >> HILO 2: Entrada Manual (Teclado consola)
        human = HumanInput(tele, comp, log)
        human.iniciar()

        log.registrar_actividad("MAIN", "✅ Todos los departamentos operativos. Sistema ONLINE.")
        print("✅ Sistema ONLINE. Entrando en bucle de control...")
        time.sleep(1) # Pequeña pausa para leer

    except Exception as e:
        print(f"❌ Error Crítico al inicio: {e}")
        log.registrar_error("MAIN", f"Fallo en arranque: {e}", critico=True)
        sys.exit(1)

    # --- C. BUCLE PRINCIPAL DE TRABAJO (The Loop) ---
    cycle_counter = 0
    current_price = 0.0
    
    # Estado Global para el Dashboard (Variables sincronizadas)
    dashboard_data = {
        'price': 0.0,
        'financials': {
            'balance': 0.0, 
            'daily_pnl': 0.0
        },
        'market': {
            'symbol': Config.SYMBOL,
            'rsi': 0.0, 
            'volumen': 0.0
        },
        'connections': {
            'binance': True, 
            'telegram': True # Ahora sí reportamos que está activo
        },
        'positions': []
    }

    try:
        while True:
            # ============================================================
            # TAREA 1: LATIDO RÁPIDO (Cada 1 seg) - CRÍTICO
            # Lectura de Precio, Auditoría de Posiciones y Actualización de Wallet
            # ============================================================
            try:
                # 1. Obtener precio real
                current_price = conn.get_ticker_price(Config.SYMBOL)
                dashboard_data['price'] = current_price
                
                if current_price > 0:
                    # 2. Contralor audita Stop Loss y Take Profits
                    comp.auditar_posiciones(current_price)
                
                # 3. Actualizar datos financieros básicos (Balance Real)
                # Nota: Para optimizar, podríamos hacer esto cada 10s, pero 1s está bien para Testnet
                dashboard_data['financials']['balance'] = fin.get_balance_total()
                dashboard_data['financials']['daily_pnl'] = fin.get_daily_pnl()

            except Exception as e:
                supervisor.reportar_error(e, "LOOP_FAST")

            # ============================================================
            # TAREA 2: LÓGICA PESADA & ESTRATEGIA (Cada 10 seg)
            # Minería de datos, Análisis Técnico y Disparos
            # ============================================================
            if cycle_counter % Config.CYCLE_SLOW == 0:
                try:
                    # 1. Sincronizar Datos (Minería Ligera)
                    # En producción real: dfs_cache = data_manager.actualizar_datos()
                    # Por ahora usamos el caché inicial, pero actualizamos métricas visuales
                    
                    if '5m' in dfs_cache and not dfs_cache['5m'].empty:
                        last_candle = dfs_cache['5m'].iloc[-1]
                        dashboard_data['market']['rsi'] = last_candle.get('rsi', 0.0)
                        dashboard_data['market']['volumen'] = last_candle.get('volume', 0.0)
                    
                    # 2. Consultar al Cerebro
                    signal = brain.analizar_mercado(dfs_cache)
                    
                    if signal:
                        # 3. Validar con Shooter (Gestor de Riesgo)
                        pos_abiertas = comp.get_open_positions_count()
                        plan = shooter.validar_y_crear_plan(signal, pos_abiertas)
                        
                        if plan:
                            # 4. EJECUCIÓN REAL
                            log.registrar_actividad("MAIN", f"⚡ Señal confirmada. Ejecutando {plan['side']}...")
                            ok, paquete = om.ejecutar_estrategia(plan)
                            
                            if ok:
                                comp.aceptar_custodia(paquete)
                                # Notificación a Telegram (Sync Exitosa)
                                msg = f"🚀 **ORDEN EJECUTADA**\nEstrategia: {plan['strategy']}\nLado: {plan['side']}\nEntrada: ${plan['entry_price']}"
                                tele.enviar_mensaje(msg)
                                log.registrar_actividad("MAIN", f"🚀 Orden {paquete['id']} enviada a mercado.")

                except Exception as e:
                    supervisor.reportar_error(e, "LOOP_SLOW")

            # ============================================================
            # TAREA 3: REPORTE VISUAL (Cada 3 seg)
            # Renderizado del Dashboard
            # ============================================================
            if cycle_counter % Config.CYCLE_DASH == 0:
                try:
                    # Actualizar lista de posiciones para la vista
                    dashboard_data['positions'] = list(comp.posiciones_activas.values())
                    
                    # Pintar en pantalla
                    dash.render(dashboard_data)
                    
                except Exception as e:
                    supervisor.reportar_error(e, "LOOP_DASH")
            
            # --- GESTIÓN DE CICLO ---
            supervisor.reportar_exito()
            time.sleep(Config.CYCLE_FAST)
            cycle_counter += 1

    except KeyboardInterrupt:
        print("\n🛑 Apagado manual solicitado...")
        log.registrar_actividad("MAIN", "Usuario solicitó detención (KeyboardInterrupt).")
        sys.exit(0)
    except Exception as e:
        supervisor.reportar_error(e, "CRITICAL_LOOP")
        sys.exit(1)

if __name__ == "__main__":
    main()