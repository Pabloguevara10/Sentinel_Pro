import threading
import sys
import time

class HumanInput:
    """
    INTERFAZ MANUAL (Teclado):
    Escucha comandos directamente en la consola del servidor.
    Útil para mantenimiento local o cierre de emergencia.
    """
    def __init__(self, telegram_bot, comptroller, logger):
        self.tele = telegram_bot
        self.comp = comptroller
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
                # input() bloquea este hilo, pero no el principal
                cmd = input() 
                self._procesar_comando(cmd.strip().lower())
            except EOFError:
                break
            except Exception as e:
                print(f"Error en input: {e}")

    def _procesar_comando(self, cmd):
        if cmd == 'help':
            print("   --- COMANDOS MANUALES ---")
            print("   status  : Ver estado de posiciones")
            print("   msg     : Enviar mensaje de prueba a Telegram")
            print("   exit    : Cerrar bot suavemente")
            print("   -------------------------")
        
        elif cmd == 'status':
            count = self.comp.get_open_positions_count()
            print(f"   [MANUAL] Posiciones abiertas: {count}")
            if count > 0:
                print(f"   {self.comp.posiciones_activas}")

        elif cmd == 'msg':
            if self.tele:
                self.tele.enviar_mensaje("👋 Hola desde la consola del servidor!")
                print("   [MANUAL] Mensaje enviado.")
            else:
                print("   [MANUAL] Telegram no está activo.")

        elif cmd == 'exit':
            print("   [MANUAL] Solicitando cierre...")
            self.log.registrar_actividad("MANUAL", "Cierre solicitado por teclado.")
            # Forzamos salida del sistema
            import os
            os._exit(0)
            
        elif cmd == '':
            pass
        else:
            print(f"   [MANUAL] Comando '{cmd}' no reconocido.")