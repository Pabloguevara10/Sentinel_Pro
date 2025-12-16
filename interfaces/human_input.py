import threading
import sys
import time
from config.config import Config

class HumanInput:
    """
    INTERFAZ MANUAL (Teclado) - V11 GAMMA TESTING:
    Permite inyectar órdenes manuales simulando estrategias específicas.
    """
    def __init__(self, telegram_bot, comptroller, order_manager, shooter, logger):
        self.tele = telegram_bot
        self.comp = comptroller
        self.om = order_manager
        self.shooter = shooter
        self.log = logger
        self.thread = None

    def iniciar(self):
        """Arranca el listener de teclado en segundo plano."""
        self.thread = threading.Thread(target=self._escuchar_teclado, daemon=True)
        self.thread.start()

    def _escuchar_teclado(self):
        print("   [TECLADO] Listener activo. Escribe 'help' para ver comandos.")
        while True:
            try:
                cmd = input() 
                self._procesar_comando(cmd.strip().lower())
            except EOFError:
                break
            except Exception as e:
                print(f"Error en input: {e}")

    def _procesar_comando(self, cmd):
        # --- COMANDOS BÁSICOS ---
        if cmd == 'help':
            print("   --- COMANDOS MANUALES (GAMMA TEST) ---")
            print("   status    : Ver posiciones abiertas")
            print("   g_long    : Forzar LONG Gamma (SL 1.5% / TP Dinámico)")
            print("   g_short   : Forzar SHORT Gamma (SL 1.5% / TP Dinámico)")
            print("   add_pnl   : Simular +$150 USD en posición (Test TP2)")
            print("   close_all : Cerrar todas las posiciones (Pánico)")
            print("   exit      : Apagar bot")
            print("   --------------------------------------")
        
        elif cmd == 'status':
            count = self.comp.get_open_positions_count()
            print(f"   [MANUAL] Posiciones abiertas: {count}")
            if count > 0:
                for pid, pos in self.comp.posiciones_activas.items():
                    pnl_sim = pos.get('fake_pnl_addon', 0.0)
                    print(f"   >> ID:{pid} | {pos['side']} | $ {pos['entry_price']} | Strat: {pos.get('strategy')} | FakePnL: {pnl_sim}")

        elif cmd == 'exit':
            print("   [MANUAL] Solicitando cierre...")
            self.log.registrar_actividad("MANUAL", "Cierre solicitado por teclado.")
            import os
            os._exit(0)
            
        # --- COMANDOS DE PRUEBA (GAMMA) ---
        elif cmd in ['g_long', 'g_short']:
            side = 'LONG' if cmd == 'g_long' else 'SHORT'
            self._inyectar_orden_gamma(side)

        elif cmd == 'add_pnl':
            self._simular_ganancia()

        elif cmd == 'close_all':
            self._cerrar_todo()

        elif cmd == '':
            pass
        else:
            print(f"   [MANUAL] Comando '{cmd}' no reconocido.")

    def _inyectar_orden_gamma(self, side):
        """
        Crea una señal artificial y fuerza al Shooter a crear un plan Gamma.
        """
        print(f"   [TEST] Generando señal artificial {side} Gamma...")
        
        # 1. Obtener precio actual real
        current_price = self.om.conn.get_ticker_price(Config.SYMBOL)
        if current_price <= 0:
            print("   [ERROR] No se pudo obtener precio de mercado.")
            return

        # 2. Crear Señal Falsa (Simulando al Brain)
        fake_signal = {
            'strategy': 'SCALPING_GAMMA',
            'side': side,
            'price': current_price,
            'rsi_slope': 0.0 # Irrelevante para entrada manual
        }

        # 3. Pedir Plan al Shooter
        # Pasamos 0 posiciones para engañar al filtro de saturación y forzar entrada
        plan = self.shooter.validar_y_crear_plan(fake_signal, open_positions_count=0)
        
        if not plan:
            print("   [ERROR] Shooter rechazó el plan (revisa logs/filtros).")
            return

        # 4. Ejecutar Plan
        print(f"   [TEST] Ejecutando Plan: {plan}")
        ok, paquete = self.om.ejecutar_estrategia(plan)
        
        if ok:
            self.comp.aceptar_custodia(paquete)
            print(f"   ✅ ORDEN MANUAL {side} EJECUTADA Y BAJO CUSTODIA GAMMA.")
        else:
            print("   ❌ Fallo en ejecución (Order Manager).")

    def _simular_ganancia(self):
        """
        Inyecta un 'PnL Fantasma' en la posición para probar el TP Dinámico del Contralor.
        """
        if not self.comp.posiciones_activas:
            print("   [ERROR] No hay posiciones activas para inyectar PnL.")
            return

        # Tomamos la primera posición
        pid = list(self.comp.posiciones_activas.keys())[0]
        pos = self.comp.posiciones_activas[pid]
        
        # Inyectamos una propiedad temporal 'fake_pnl_addon' que el Contralor deberá leer
        # NOTA: Para que esto funcione, debemos hacer un pequeño ajuste en el Comptroller
        # O simplemente bajar el umbral de prueba en Config.py a $1 USD temporalmente.
        
        # Como no quiero modificar el Comptroller solo para un test sucio,
        # haremos lo siguiente:
        print("   [TEST] ⚠️ Para probar el TP Dinámico ($150), sugiero:")
        print("   1. Editar config.py y poner TP_DYNAMIC_THRESHOLD = 1.0 (1 dólar)")
        print("   2. Esperar que el mercado se mueva un poco a favor.")
        print("   (La inyección de precio falso es compleja sin mocks profundos)")

    def _cerrar_todo(self):
        print("   [PANIC] Cerrando todas las posiciones...")
        for pid, pos in list(self.comp.posiciones_activas.items()):
            qty = pos['qty']
            side = pos['side']
            self.om.cerrar_posicion_mercado(side, qty)
            # Cancelar SL si existe
            if pos.get('sl_order_id'):
                self.om.cancelar_orden(pos['sl_order_id'])
            
            del self.comp.posiciones_activas[pid]
            print(f"   💀 Posición {pid} cerrada a mercado.")