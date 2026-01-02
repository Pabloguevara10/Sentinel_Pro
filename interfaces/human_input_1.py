# =============================================================================
# UBICACIÓN: interfaces/human_input.py
# DESCRIPCIÓN: CONSOLA TÁCTICA V17.9 (COMPATIBLE CON TRIAD SHOOTER)
# =============================================================================

import threading
import sys
from config.config import Config # Importamos config para acceso global si hace falta

class HumanInput:
    """
    CONSOLA TÁCTICA MANUAL:
    - Actúa como un 'Brain' manual.
    - Envía señales con los nombres CORRECTOS (GAMMA, SHADOW) para que Shooter las acepte.
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
        self.thread = threading.Thread(target=self._escuchar_teclado, daemon=True)
        self.thread.start()
        print("⌨️  [COMMANDER] Consola Táctica Lista. Escribe 'help' para comandos.")

    def _escuchar_teclado(self):
        while self.running:
            try:
                # Lectura no bloqueante idealmente, pero input() bloquea el hilo (ok en daemon)
                if sys.platform == 'win32':
                    pass # En windows input() es estándar
                
                cmd = input().strip().lower()
                if not cmd: continue
                self._procesar_comando(cmd)
            except EOFError: break
            except Exception as e:
                # Evitar spam de error en cierre
                if self.running: print(f"⚠️ Error Input: {e}")

    def _procesar_comando(self, cmd):
        # --- COMANDOS DE DISPARO (MOCK BRAIN) ---
        # Mapeamos comandos a las estrategias REALES de la Tríada
        
        # 'l' / 's' -> GAMMA (Entrada Rápida / Market)
        if cmd == 'l':  self._inyectar_flujo('LONG', 'GAMMA', 'MANUAL_GAMMA')
        elif cmd == 's': self._inyectar_flujo('SHORT', 'GAMMA', 'MANUAL_GAMMA')
        
        # 'shl' / 'shs' -> SHADOW (Entrada Limit / Reversión)
        # Nota: Shadow requiere ATR, lo simularemos
        elif cmd == 'shl': self._inyectar_flujo('LONG', 'SHADOW', 'MANUAL_SHADOW')
        elif cmd == 'shs': self._inyectar_flujo('SHORT', 'SHADOW', 'MANUAL_SHADOW')
        
        # 'swl' -> SWING (Entrada Limit / Estructural)
        elif cmd == 'swl': self._inyectar_flujo('LONG', 'SWING', 'MANUAL_SWING')
        
        # --- COMANDOS DE GESTIÓN ---
        elif cmd == 'panic': self._protocolo_panico()
        elif cmd == 'status': self._mostrar_status()
        elif cmd == 'bal': print(f"💰 Balance: ${self.fin.get_balance_total():.2f}")
        elif cmd == 'help': self._mostrar_ayuda()
        elif cmd == 'exit': 
            print("🛑 Cerrando interfaz manual...")
            self.running = False
            # Opcional: Cerrar todo el bot
            # sys.exit(0) 
        else:
            print("❌ Comando desconocido. Usa 'help'.")

    def _inyectar_flujo(self, side, strategy_name, mode_tag):
        """
        Simula ser el Brain. Crea una señal y la pasa al Shooter.
        """
        print(f"⚡ Iniciando secuencia manual: {strategy_name} ({side})...")
        
        # Obtenemos precio actual de referencia
        # Si order_manager no tiene precio reciente, usamos 0 (Shooter o Director validarán)
        # Idealmente obtenerlo de API, pero para mock usamos 0 o un fetch rápido
        try:
            precio_ref = self.om.api.get_ticker_price(Config.SYMBOL)
        except:
            precio_ref = 0.0

        if precio_ref == 0:
            print("⚠️ No se pudo obtener precio actual. La orden podría fallar.")

        # 1. Crear la Señal Sintética (Con formato del Brain)
        senal_sintetica = {
            'timestamp': 0, # Se llena en ejecución
            'strategy': strategy_name, # AHORA SÍ COINCIDE (GAMMA/SHADOW/SWING)
            'signal': side, 
            'mode': mode_tag,
            'confidence': 1.0, 
            'price': precio_ref,
            'atr': precio_ref * 0.01 # Mock de ATR (1%) para que Shadow no falle cálculo
        }

        # 2. Validación del Shooter
        # Pasamos las posiciones activas para que valide cupos
        plan = self.shooter.validar_y_crear_plan(senal_sintetica, self.comp.posiciones_activas)

        if plan:
            print(f"✅ Shooter Aprobó: {plan['qty']} tokens @ {side} ({plan['execution_type']})")
            
            # 3. Ejecución
            exito, paquete = self.om.ejecutar_estrategia(plan)
            
            if exito and paquete:
                # 4. Custodia
                self.comp.aceptar_custodia(paquete)
                
                msg_exito = (f"🚀 MANUAL OK: {strategy_name} | ${paquete['entry_price']}")
                print(msg_exito)
                self.tele.enviar_mensaje(msg_exito)
                self.log.registrar_actividad("MANUAL", f"Entrada OK: {strategy_name}")
            else:
                print("❌ Error en ejecución (API/OM) - Revisa logs.")
        else:
            print(f"⛔ Shooter RECHAZÓ la señal '{strategy_name}'.")
            print("   (Causa probable: Cupos llenos, Estrategia desconocida o Error de configuración)")

    def _protocolo_panico(self):
        print("\n🚨🚨 ALERTA ROJA: PÁNICO ACTIVADO 🚨🚨")
        self.tele.enviar_mensaje("🚨 EJECUTANDO PROTOCOLO DE PÁNICO MANUAL")
        self.om.cerrar_posicion(self.om.cfg.SYMBOL, reason="PANIC_CLI")
        self.comp.posiciones_activas.clear()
        print("✅ PÁNICO FINALIZADO.")

    def _mostrar_status(self):
        self.comp.sincronizar_con_exchange() 
        print(f"\n📊 ESTATUS ({len(self.comp.posiciones_activas)} Posiciones)")
        for key, p in self.comp.posiciones_activas.items():
            print(f"   🔹 {p['symbol']} {p['side']} | Entry: {p['entry_price']} | PnL: {p.get('pnl_pct',0)*100:.2f}% | Strat: {p.get('strategy')}")

    def _mostrar_ayuda(self):
        print("\n🔰 COMANDOS DE COMBATE V17.9 (TRIAD COMPATIBLE) 🔰")
        print(" l      : Disparar GAMMA LONG  (Market)")
        print(" s      : Disparar GAMMA SHORT (Market)")
        print(" shl    : Disparar SHADOW LONG (Limit)")
        print(" shs    : Disparar SHADOW SHORT (Limit)")
        print(" status : Ver posiciones")
        print(" panic  : ⚠️ CERRAR TODO")
        print(" exit   : Salir")