import time
import sys
import os

# --- IMPORTACIONES ---
from config.config import Config
from logs.system_logger import SystemLogger
from connections.api_manager import APIManager
from execution.order_manager import OrderManager
from execution.comptroller import Comptroller
from logic.brain import Brain
from logic.shooter import Shooter
from data.historical_manager import HistoricalManager

# --- INTERFACES ---
from interfaces.dashboard import Dashboard
from interfaces.telegram_bot import TelegramBot

class SentinelBot:
    """
    NÚCLEO CENTRAL (V12.6 - FIX INTERFACES):
    - Telegram: Inyección de dependencias corregida.
    - Dashboard: Mapeo de claves corregido ('volumen', 'binance').
    """
    def __init__(self):
        # 1. Inicialización de Infraestructura
        Config.inicializar_infraestructura()
        
        self.logger = SystemLogger()
        self.logger.registrar_actividad("MAIN", f"🤖 INICIANDO {Config.BOT_NAME}...")

        # 2. Inicialización de Capa de Ejecución
        try:
            self.api = APIManager(self.logger)
            self.order_manager = OrderManager(Config, self.api, self.logger)
            # El Contralor necesita OrderManager y API
            self.comptroller = Comptroller(Config, self.order_manager, self.api, self.logger)
        except Exception as e:
            self.logger.registrar_error("MAIN", f"Fallo en Capa de Ejecución: {e}", critico=True)
            sys.exit(1)

        # 3. Inicialización de Capa Lógica y Datos
        self.data_miner = HistoricalManager(self.api, self.logger)
        self.brain = Brain(Config)
        
        # 4. Puente Financiero (Necesario para Shooter y Telegram)
        class FinancialsBridge:
            def __init__(self, api_ref):
                self.api = api_ref
            
            def get_balance_total(self):
                try:
                    acc = self.api.client.account()
                    for asset in acc['assets']:
                        if asset['asset'] == 'USDT':
                            return float(asset['walletBalance'])
                except:
                    pass
                return 0.0
            
            def get_daily_pnl(self):
                return 0.0 # Implementar lógica real si se desea

        self.fin_bridge = FinancialsBridge(self.api)
        self.shooter = Shooter(Config, self.logger, self.fin_bridge)
        
        # 5. Inicialización de Interfaces
        self.dashboard = Dashboard()
        
        # --- FIX TELEGRAM: Inyección correcta de dependencias ---
        # TelegramBot pide: (config, shooter, comptroller, order_manager, logger, financials)
        try:
            self.telegram = TelegramBot(
                Config, 
                self.shooter, 
                self.comptroller, 
                self.order_manager, 
                self.logger, 
                self.fin_bridge
            )
            # Intentamos iniciar (esto lanza el hilo)
            self.telegram.iniciar()
            self.telegram_active = True
        except Exception as e:
            self.logger.registrar_error("MAIN", f"Telegram no pudo iniciar: {e}")
            self.telegram = None
            self.telegram_active = False

    def inicializar_sistema(self):
        self.logger.registrar_actividad("MAIN", "--- FASE DE SINCRONIZACIÓN INICIAL ---")
        
        # Sincronización de Datos
        print("⏳ Sincronizando datos históricos...")
        exito_datos = self.data_miner.sincronizar_infraestructura_datos()
        
        if not exito_datos:
            self.logger.registrar_error("MAIN", "⛔ Fallo crítico en datos. Deteniendo.")
            sys.exit(1)

        # Sincronización de Contralor
        self.comptroller.sincronizar_con_exchange()
        
        self.logger.registrar_actividad("MAIN", "✅ Sistema listo.")
        
        # Notificación Telegram
        if self.telegram_active:
            self.telegram.enviar_mensaje(f"🤖 **SENTINEL ONLINE**\n✅ Sistemas Operativos\n📊 Par: {Config.SYMBOL}")

    def run(self):
        self.inicializar_sistema()
        self.logger.registrar_actividad("MAIN", "--- BUCLE PRINCIPAL ---")
        
        last_analysis = 0
        last_sync = 0
        last_dash = 0
        
        SYNC_INTERVAL = 60
        DASH_INTERVAL = 3

        try:
            while True:
                now = time.time()

                # 1. DATA SYNC (60s)
                if now - last_sync >= SYNC_INTERVAL:
                    self.data_miner.sincronizar_infraestructura_datos()
                    last_sync = now

                # 2. AUDITORIA (1s)
                self.comptroller.auditar_posiciones_activas()

                # 3. DASHBOARD (3s)
                if now - last_dash >= DASH_INTERVAL:
                    self._actualizar_dashboard()
                    last_dash = now
                
                # 4. ANALISIS (10s)
                if now - last_analysis >= Config.CYCLE_SLOW:
                    self._ciclo_analisis()
                    last_analysis = now
                
                time.sleep(Config.CYCLE_FAST)
                
        except KeyboardInterrupt:
            print("\n🛑 Apagando...")
            sys.exit(0)
        except Exception as e:
            self.logger.registrar_error("MAIN", f"Error Loop: {e}", critico=True)

    def _actualizar_dashboard(self):
        try:
            # Datos de Mercado
            df_15m = self.data_miner.obtener_dataframe_cache('15m')
            rsi = 0.0
            vol = 0.0
            
            if not df_15m.empty:
                last_row = df_15m.iloc[-1]
                rsi = last_row.get('rsi', 0.0)
                vol = last_row.get('volume', 0.0) # Aquí leemos 'volume' del DF
            
            # Datos Financieros y API
            price = self.api.get_ticker_price(Config.SYMBOL)
            balance = self.fin_bridge.get_balance_total()
            
            # --- FIX: MAPEO DE CLAVES PARA DASHBOARD.PY ---
            dashboard_data = {
                'price': price,
                'financials': {
                    'balance': balance,
                    'daily_pnl': 0.0 
                },
                'market': {
                    'symbol': Config.SYMBOL,
                    'rsi': rsi,
                    'volumen': vol  # <--- FIX: Clave renombrada a 'volumen'
                },
                'connections': {
                    'binance': (price > 0),    # <--- FIX: Clave renombrada a 'binance'
                    'telegram': self.telegram_active
                },
                'positions': list(self.comptroller.posiciones_activas.values())
            }
            
            self.dashboard.render(dashboard_data)

        except Exception:
            pass

    def _ciclo_analisis(self):
        df_15m = self.data_miner.obtener_dataframe_cache('15m')
        if df_15m.empty: return

        cache = {'15m': df_15m}
        senal = self.brain.analizar_mercado(cache)
        
        if senal:
            posiciones = self.comptroller.posiciones_activas
            plan = self.shooter.validar_y_crear_plan(senal, posiciones)
            
            if plan:
                exito, paquete = self.order_manager.ejecutar_estrategia(plan)
                if exito and paquete:
                    self.comptroller.aceptar_custodia(paquete)
                    if self.telegram_active:
                        msg = f"🚀 **ORDEN EJECUTADA**\n{plan['side']} @ ${plan['entry_price']}"
                        self.telegram.enviar_mensaje(msg)

if __name__ == "__main__":
    bot = SentinelBot()
    bot.run()