# =============================================================================
# UBICACIÓN: interfaces/human_input.py
# DESCRIPCIÓN: CONSOLA TÁCTICA V18.0 (GAMMA MANUAL COMMANDER)
# =============================================================================

import threading
import sys
from config.config import Config 

class HumanInput:
    """
    CONSOLA TÁCTICA V18:
    - Permite inyección manual de órdenes GAMMA.
    - Asegura el etiquetado correcto (GAMMA_NORMAL) para aplicar SL del 2%.
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
        print("⌨️  [COMMANDER V18] Consola Lista. 'l'=Long, 's'=Short, 'panic'=Cerrar Todo.")

    def _escuchar_teclado(self):
        while self.running:
            try:
                if sys.platform == 'win32': pass 
                
                cmd = input().strip().lower()
                if not cmd: continue
                self._procesar_comando(cmd)
            except EOFError: break
            except Exception as e:
                if self.running: print(f"⚠️ Error Input: {e}")

    def _procesar_comando(self, cmd):
        # --- COMANDOS GAMMA V4.6 ---
        # l/s -> Gamma Normal (SL 2.0%)
        if cmd == 'l':  self._inyectar_flujo('LONG', 'GAMMA', 'GAMMA_NORMAL')
        elif cmd == 's': self._inyectar_flujo('SHORT', 'GAMMA', 'GAMMA_NORMAL')
        
        # hl/hs -> Gamma Hedge (SL 1.5% - Sniper Manual)
        elif cmd == 'hl': self._inyectar_flujo('LONG', 'GAMMA', 'GAMMA_HEDGE')
        elif cmd == 'hs': self._inyectar_flujo('SHORT', 'GAMMA', 'GAMMA_HEDGE')
        
        # --- GESTIÓN ---
        elif cmd == 'panic': self._protocolo_panico()
        elif cmd == 'status': self._mostrar_status()
        elif cmd == 'bal': print(f"💰 Balance: ${self.fin.get_balance_total():.2f}")
        elif cmd == 'help': self._mostrar_ayuda()
        elif cmd == 'exit': 
            print("🛑 Cerrando interfaz manual...")
            self.running = False
        else:
            print("❌ Comando desconocido. Usa 'help'.")

    def _inyectar_flujo(self, side, strategy_name, mode_tag):
        """
        Crea señal sintética para el Shooter.
        """
        print(f"⚡ Iniciando secuencia manual: {strategy_name} [{mode_tag}] ({side})...")
        
        try:
            precio_ref = self.om.api.get_ticker_price(Config.SYMBOL)
        except:
            precio_ref = 0.0

        if precio_ref == 0:
            print("⚠️ No se pudo obtener precio actual. Intentando a ciegas (Market)...")

        # 1. Crear Señal
        senal_sintetica = {
            'timestamp': 0, 
            'strategy': strategy_name,
            'signal': side, 
            'mode': mode_tag, # CRÍTICO: Debe contener 'NORMAL' o 'HEDGE'
            'confidence': 1.0, 
            'price': precio_ref
        }

        # 2. Validación Shooter
        plan = self.shooter.validar_y_crear_plan(senal_sintetica, self.comp.posiciones_activas)

        if plan:
            print(f"✅ Shooter Aprobó: {plan['qty']} tokens @ {side}")
            
            # 3. Ejecución
            exito, paquete = self.om.ejecutar_estrategia(plan)
            
            if exito and paquete:
                # 4. Custodia
                self.comp.aceptar_custodia(paquete)
                
                msg = (f"🚀 MANUAL OK: {side} | Entry: {paquete['entry_price']} | SL: {paquete['sl_price']}")
                print(msg)
                self.tele.enviar_mensaje(msg)
                self.log.registrar_actividad("MANUAL", f"Entrada OK: {strategy_name}")
            else:
                print("❌ Error en ejecución (API/OM).")
        else:
            print(f"⛔ Shooter RECHAZÓ la señal (Cupos llenos o Riesgo).")

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
            print(f"   🔹 {p['symbol']} {p['side']} | Entry: {p['entry_price']} | PnL: {p.get('pnl_pct',0)*100:.2f}% | SL: {p.get('sl_price')}")

    def _mostrar_ayuda(self):
        print("\n🔰 COMANDOS GAMMA V18 🔰")
        print(" l      : Gamma Normal LONG  (SL 2.0%)")
        print(" s      : Gamma Normal SHORT (SL 2.0%)")
        print(" hl     : Gamma Hedge LONG   (SL 1.5%)")
        print(" hs     : Gamma Hedge SHORT  (SL 1.5%)")
        print(" status : Ver posiciones")
        print(" panic  : ⚠️ CERRAR TODO")