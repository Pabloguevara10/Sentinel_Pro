# =============================================================================
# UBICACIÓN: interfaces/telegram_bot.py
# DESCRIPCIÓN: TELEGRAM BOT V19.0 (CON REPORTE DE INTENCIÓN DETALLADO)
# =============================================================================

import threading
import time
import requests
from config.config import Config

class TelegramBot:
    """
    COMANDANTE TELEGRAM V19:
    - Control Remoto para Gamma V4.6.
    - Reporte de Intención de Entrada (Pre-Trade).
    - Reporte de Ejecución y Pánico.
    """
    def __init__(self, config, shooter, comptroller, order_manager, logger, financials):
        self.cfg = config
        self.shooter = shooter
        self.comp = comptroller
        self.om = order_manager
        self.log = logger
        self.fin = financials
        
        self.token = config.TELEGRAM_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.running = False

    def iniciar(self):
        if not self.token or not self.chat_id:
            self.log.registrar_error("TELEGRAM", "Credenciales vacías.")
            return

        self.running = True
        t = threading.Thread(target=self._poll_updates, daemon=True)
        t.start()
        self.enviar_mensaje(f"🤖 **{self.cfg.BOT_NAME}** Online\nVersión: {self.cfg.VERSION}\nModo: {Config.MODE}")

    def enviar_mensaje(self, texto):
        if not self.running: return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = {"chat_id": self.chat_id, "text": texto, "parse_mode": "Markdown"}
        try:
            requests.post(url, data=data, timeout=5)
        except Exception as e:
            self.log.registrar_error("TELEGRAM", f"Fallo envío: {e}")

    # --- NUEVA FUNCIÓN DE REPORTE DE INTENCIÓN ---
    def reportar_intencion_entrada(self, plan):
        """
        Envía un reporte detallado con los parámetros calculados por Shooter
        ANTES de que la orden sea ejecutada en Binance.
        """
        if not self.running: return
        
        try:
            side = plan.get('side', 'UNKNOWN')
            strat = plan.get('strategy', 'UNKNOWN')
            entry = float(plan.get('entry_price', 0))
            sl = float(plan.get('sl_price', 0))
            
            # Extraer TPs de la lista dinámica
            tp1 = "N/A"
            tp2 = "N/A"
            
            if 'tp_map' in plan:
                for tp in plan['tp_map']:
                    if tp.get('id') == 'TP1': tp1 = f"{tp['price_target']:.2f}"
                    if tp.get('id') == 'TP2': tp2 = f"{tp['price_target']:.2f}"
            
            # Calcular % de Riesgo para contexto visual
            sl_pct = 0
            if entry > 0:
                if side == 'LONG': sl_pct = (entry - sl) / entry * 100
                else: sl_pct = (sl - entry) / entry * 100
                
            emoji = "📈" if side == 'LONG' else "📉"
            
            msg = (
                f"⚡ **AUTORIZACIÓN {strat}**\n"
                f"{emoji} **{side}** @ {entry:.2f}\n"
                f"🛡️ **S/L:** {sl:.2f} ({sl_pct:.2f}%)\n"
                f"🎯 **TP1:** {tp1}\n"
                f"🎯 **TP2:** {tp2}\n"
                f"_⏳ Enviando orden a Binance..._"
            )
            self.enviar_mensaje(msg)
            
        except Exception as e:
            self.log.registrar_error("TELEGRAM", f"Error armando reporte intención: {e}")

    def _poll_updates(self):
        offset = 0
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        
        while self.running:
            try:
                # Long polling
                resp = requests.get(url, params={"offset": offset, "timeout": 20}, timeout=30)
                if resp.status_code == 200:
                    result = resp.json().get("result", [])
                    for update in result:
                        offset = update["update_id"] + 1
                        if "message" in update and "text" in update["message"]:
                            self._procesar_comando(update["message"]["text"])
            except Exception:
                time.sleep(5)
            time.sleep(0.5)

    def _procesar_comando(self, texto):
        cmd = texto.strip().lower()
        
        # --- COMANDOS OPERATIVOS ---
        if cmd == '/long': self._inyectar_senal('LONG', 'GAMMA', 'GAMMA_NORMAL')
        elif cmd == '/short': self._inyectar_senal('SHORT', 'GAMMA', 'GAMMA_NORMAL')
        elif cmd == '/panic': self._protocolo_panico()
        
        # --- COMANDOS INFORMATIVOS ---
        elif cmd == '/status': self._reportar_status()
        elif cmd == '/balance': 
            bal = self.fin.get_balance_total()
            self.enviar_mensaje(f"💰 Balance: **${bal:,.2f}**")
        elif cmd == '/help': self._enviar_ayuda()

    def _inyectar_senal(self, side, strategy_name, mode_tag):
        self.enviar_mensaje(f"⚡ Procesando **{side}** ({mode_tag})...")
        
        try: price = self.om.api.get_ticker_price(self.cfg.SYMBOL)
        except: price = 0
        
        senal = {
            'timestamp': 0, 'strategy': strategy_name,
            'signal': side, 'mode': mode_tag,
            'confidence': 1.0, 'price': price
        }
        
        plan = self.shooter.validar_y_crear_plan(senal, self.comp.posiciones_activas)
        
        if plan:
            # Reportamos intención también en manual
            self.reportar_intencion_entrada(plan)
            
            exito, paquete = self.om.ejecutar_estrategia(plan)
            
            if exito and paquete:
                self.comp.aceptar_custodia(paquete)
                self.log.registrar_actividad("TELEGRAM", f"Orden Remota OK: {side}")
                self.enviar_mensaje("✅ **Orden Confirmada en Exchange**")
            else:
                self.enviar_mensaje("❌ Fallo en la ejecución (API/OM).")
        else:
            self.enviar_mensaje("⛔ **Shooter RECHAZÓ la orden.**\n(Cupos llenos o Riesgo alto)")

    def _protocolo_panico(self):
        self.enviar_mensaje("🚨 **PÁNICO RECIBIDO: CERRANDO TODO**")
        self.om.cerrar_posicion(self.cfg.SYMBOL, reason="TELEGRAM_PANIC")
        self.comp.posiciones_activas.clear()
        self.enviar_mensaje("✅ Posiciones cerradas y memoria limpia.")

    def _reportar_status(self):
        self.comp.sincronizar_con_exchange()
        if not self.comp.posiciones_activas:
            self.enviar_mensaje("💤 Sin posiciones activas.")
            return
            
        msg = "📊 **POSICIONES ACTIVAS**\n"
        for pid, p in self.comp.posiciones_activas.items():
            pnl = p.get('pnl_pct', 0) * 100
            msg += f"🔹 {p['side']} | PnL: {pnl:+.2f}% | SL: {p.get('sl_price')}\n"
        self.enviar_mensaje(msg)

    def _enviar_ayuda(self):
        msg = (
            "🔰 **COMANDOS V19** 🔰\n\n"
            "/long - Gamma Normal LONG\n"
            "/short - Gamma Normal SHORT\n"
            "/status - Ver PnL y SL\n"
            "/balance - Ver Saldo USDT\n"
            "/panic - 🚨 CERRAR TODO"
        )
        self.enviar_mensaje(msg)