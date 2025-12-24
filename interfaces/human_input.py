# =============================================================================
# UBICACIÓN: interfaces/human_input.py
# DESCRIPCIÓN: CONSOLA TÁCTICA V15 (MOCKING BRAIN MODE)
# =============================================================================

import threading
import time
from config.config import Config

class HumanInput:
    """
    INTERFAZ MANUAL DE COMBATE (CLI):
    Permite inyectar señales 'sintéticas' que imitan al Brain.
    El Shooter las recibe y las procesa como si fueran automáticas.
    """
    def __init__(self, telegram_bot, comptroller, order_manager, shooter, logger, financials):
        self.tele = telegram_bot
        self.comp = comptroller
        self.om = order_manager
        self.shooter = shooter
        self.log = logger
        self.fin = financials 
        self.thread = None
        self.running = True

    def iniciar(self):
        """Arranca el listener de teclado en hilo independiente (Daemon)."""
        self.thread = threading.Thread(target=self._escuchar_teclado, daemon=True)
        self.thread.start()
        print("⌨️  [COMMANDER] Consola Táctica Lista. Escribe 'help' para comandos.")

    def _escuchar_teclado(self):
        """Bucle infinito que espera input del usuario sin bloquear al bot."""
        while self.running:
            try:
                # El input bloquea este hilo, pero no al Main Loop del bot
                cmd = input() 
                if cmd.strip():
                    self._procesar_comando(cmd.strip().lower())
            except EOFError:
                break
            except Exception as e:
                print(f"❌ Error CLI: {e}")

    def _procesar_comando(self, cmd):
        # --- COMANDOS DE INFORMACIÓN ---
        if cmd == 'help':
            self._mostrar_ayuda()
        elif cmd in ['stat', 'status']:
            self._mostrar_status()
        elif cmd in ['bal', 'balance']:
            bal = self.fin.get_balance_total()
            print(f"💰 Balance Disponible: ${bal:,.2f} USDT")

        # --- COMANDOS DE DISPARO (TRÍADA) ---
        # Shadow Hunter (La Estrella)
        elif cmd == 'shl': self._inyectar_senal('SHADOW_HUNTER_V2', 'LONG')
        elif cmd == 'shs': self._inyectar_senal('SHADOW_HUNTER_V2', 'SHORT')
        
        # Swing (Legacy)
        elif cmd == 'swl': self._inyectar_senal('TREND_FOLLOWING', 'LONG')
        elif cmd == 'sws': self._inyectar_senal('TREND_FOLLOWING', 'SHORT')
        
        # Gamma (Legacy) - Si quisieras activarlo
        elif cmd == 'gl': self._inyectar_senal('GAMMA_V7', 'LONG')
        elif cmd == 'gs': self._inyectar_senal('GAMMA_V7', 'SHORT')

        # --- COMANDOS DE EMERGENCIA ---
        elif cmd == 'panic':
            self._protocolo_panico()
        
        else:
            print(f"⚠️ Comando '{cmd}' desconocido. Usa 'help'.")

    def _inyectar_senal(self, estrategia_key, side):
        """
        Construye una señal IDÉNTICA a la que generaría el Brain
        y se la pasa al Shooter.
        """
        print(f"🧪 Preparando inyección: {estrategia_key} {side}...")
        
        # 1. Obtener Precio Real (Necesario para el paquete)
        try:
            precio_actual = self.om.api.get_real_price(Config.SYMBOL)
            if not precio_actual:
                print("❌ Error: API no devolvió precio.")
                return
        except Exception as e:
            print(f"❌ Error obteniendo precio: {e}")
            return

        # 2. Construir Paquete de Señal (MOCKING THE BRAIN)
        # Esta estructura engaña al Shooter para que crea que es una señal válida
        fake_signal = {
            'strategy': estrategia_key, # Clave para que Shooter busque en Config
            'side': side,
            'price': precio_actual,
            'ts': time.time(),
            'sl_match': None,     # Shadow usa SL% calculado por Shooter
            'confidence': 'HIGH', # Forzamos confianza alta
            'origin': 'CLI'       # Marca de agua para logs
        }

        # 3. Enviar al Shooter
        print(f"📨 Enviando señal sintética al Shooter @ ${precio_actual}")
        
        # AQUÍ ESTÁ LA MAGIA: Usamos el método estándar.
        # El Shooter hará las validaciones de saldo, overlap y ejecución.
        resultado = self.shooter.ejecutar_senal(fake_signal)
        
        if resultado:
            print(f"✅ Shooter aceptó la señal.")
            self.log.registrar_actividad("MANUAL", f"Inyección CLI: {estrategia_key} {side}")
        else:
            print("⛔ Shooter rechazó la señal (Ver logs para motivo).")

    def _protocolo_panico(self):
        print("\n🚨🚨 INICIANDO PROTOCOLO DE PÁNICO 🚨🚨")
        print("1. Cancelando todas las órdenes pendientes...")
        self.om.cancelar_todo()
        
        print("2. Cerrando posición a mercado...")
        self.om.cerrar_posicion(Config.SYMBOL, reason="PANIC_CLI")
            
        print("✅ PÁNICO FINALIZADO. Sistema limpio.")

    def _mostrar_status(self):
        # Asumiendo que Comptroller tiene un método para ver posiciones
        # Si no, imprime un mensaje genérico
        try:
            pos = self.comp.posiciones_activas
            print(f"\n📊 ESTATUS ACTUAL ({len(pos)} Posiciones)")
            for pid, p in pos.items():
                print(f"   🔹 {pid} | {p['side']} | Entry: {p['entry_price']}")
        except:
            print("📊 Sin información detallada de posiciones.")
        print("")

    def _mostrar_ayuda(self):
        print("\n🔰 COMANDOS DE COMBATE V8.5 🔰")
        print(" shl  : Shadow LONG     |  shs  : Shadow SHORT")
        print(" swl  : Swing LONG      |  sws  : Swing SHORT")
        print(" stat : Ver Estado      |  bal  : Ver Saldo")
        print(" panic: 🚨 CERRAR TODO INMEDIATAMENTE")
        print("---------------------------------------------")