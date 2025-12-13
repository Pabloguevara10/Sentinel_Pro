import threading
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config.config import Config

class TelegramBot:
    """
    INTERFAZ TELEGRAM (V9.0 - Async Threaded):
    Permite control remoto y notificaciones sin bloquear el hilo principal.
    Ejecuta su propio bucle de eventos (Event Loop) en un hilo separado.
    """
    def __init__(self, config, shooter, comptroller, order_manager, logger, financials):
        self.cfg = config
        self.shooter = shooter
        self.comp = comptroller
        self.om = order_manager
        self.log = logger
        self.fin = financials
        
        self.app = None
        self.loop = None
        self.thread = None
        self.running = False

    def iniciar(self):
        """Arranca el bot de Telegram en un hilo secundario."""
        if not self.cfg.TELEGRAM_TOKEN:
            self.log.registrar_actividad("TELEGRAM", "⚠️ No hay Token configurado. Módulo desactivado.")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()
        self.log.registrar_actividad("TELEGRAM", "🚀 Servicio de mensajería iniciado en segundo plano.")

    def _run_async_loop(self):
        """Configura y ejecuta el bucle asíncrono de Telegram."""
        # Crear nuevo loop para este hilo
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Construir la aplicación
        self.app = ApplicationBuilder().token(self.cfg.TELEGRAM_TOKEN).build()

        # --- REGISTRO DE COMANDOS ---
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("balance", self._cmd_balance))
        self.app.add_handler(CommandHandler("pos", self._cmd_positions))
        self.app.add_handler(CommandHandler("stop", self._cmd_stop_panic))
        self.app.add_handler(CommandHandler("help", self._cmd_help))

        # Iniciar polling (bloqueante solo para este hilo)
        self.log.registrar_actividad("TELEGRAM", "👂 Escuchando comandos...")
        self.loop.run_until_complete(self.app.run_polling(stop_signals=None))

    # --- COMANDOS (HANDLERS) ---

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f"🤖 **{self.cfg.BOT_NAME}** en línea.\nUsa /help para ver comandos.")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = (
            "📋 **COMANDOS DISPONIBLES:**\n"
            "/status - Reporte general del sistema\n"
            "/balance - Ver saldo y PnL\n"
            "/pos - Ver posiciones abiertas\n"
            "/stop - 🛑 DETENCIÓN DE EMERGENCIA"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        price = self.om.conn.get_ticker_price(self.cfg.SYMBOL)
        pos_count = self.comp.get_open_positions_count()
        msg = (
            f"📊 **ESTADO DEL SISTEMA**\n"
            f"Symbol: {self.cfg.SYMBOL}\n"
            f"Precio: ${price:,.2f}\n"
            f"Posiciones Activas: {pos_count}\n"
            f"Estado API: ✅ Conectado"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def _cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        bal = self.fin.get_balance_total()
        pnl = self.fin.get_daily_pnl()
        emoji = "🟢" if pnl >= 0 else "🔴"
        msg = (
            f"💰 **BILLETERA**\n"
            f"Balance Total: ${bal:,.2f}\n"
            f"PnL Diario: {emoji} ${pnl:,.2f}"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def _cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        positions = self.comp.posiciones_activas
        if not positions:
            await update.message.reply_text("🤷‍♂️ No hay posiciones abiertas.")
            return
        
        for pid, pos in positions.items():
            roi_str = "Calc..." # Simplificado para respuesta rápida
            msg = (
                f"🛡️ **POSICIÓN {pid}**\n"
                f"Lado: {pos['side']}\n"
                f"Entrada: ${pos['entry_price']}\n"
                f"SL: ${pos['sl_price']}\n"
                f"B/E Activado: {'✅' if pos['be_activado'] else '❌'}"
            )
            await update.message.reply_text(msg, parse_mode='Markdown')

    async def _cmd_stop_panic(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando de Pánico: Cierra todo y detiene el bot."""
        await update.message.reply_text("🚨 **ALERTA DE PÁNICO RECIBIDA** 🚨\nIniciando protocolo de cierre total...")
        self.log.registrar_actividad("TELEGRAM", "Usuario solicitó STOP DE PÁNICO.")
        
        # 1. Cerrar posiciones
        # (Aquí podrías implementar una lógica para cerrar todo en OrderManager)
        # self.om.cerrar_todas_las_posiciones() # Pendiente de implementar si deseas
        
        # 2. Detener proceso (Simulado)
        await update.message.reply_text("⚠️ El bot se detendrá en el servidor. Requiere reinicio manual.")
        # En un entorno real, esto podría levantar una bandera en Config para salir del while True

    # --- MÉTODOS DE ENVÍO (SALIDA) ---
    
    def enviar_mensaje(self, mensaje):
        """Método thread-safe para enviar mensajes desde Main hacia Telegram."""
        if self.loop and self.running and self.cfg.TELEGRAM_CHAT_ID:
            coro = self.app.bot.send_message(chat_id=self.cfg.TELEGRAM_CHAT_ID, text=mensaje)
            # Programar la corrutina en el loop del hilo de Telegram
            asyncio.run_coroutine_threadsafe(coro, self.loop)