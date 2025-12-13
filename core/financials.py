import time
from datetime import datetime
from config.config import Config

class Financials:
    """
    DEPARTAMENTO FINANCIERO:
    Gestiona la billetera, monitorea el balance en tiempo real
    y lleva la contabilidad del PnL diario (Profit & Loss).
    """
    def __init__(self, config, api_manager):
        self.cfg = config
        self.conn = api_manager
        
        # Estado Financiero
        self.initial_balance = 0.0
        self.current_balance = 0.0
        self.daily_pnl = 0.0
        self.max_daily_loss = 0.0
        
        # Inicialización
        self._sincronizar_billetera_inicial()

    def _sincronizar_billetera_inicial(self):
        """Obtiene el saldo inicial al arrancar el bot."""
        self.initial_balance = self.get_balance_total()
        # Calculamos el límite de pérdida diaria (ej. 5% del capital inicial)
        # Asumimos que Config tiene MAX_DAILY_LOSS_PCT, si no, usamos 0.05 por defecto
        max_loss_pct = getattr(self.cfg, 'MAX_DAILY_LOSS_PCT', 0.05)
        self.max_daily_loss = self.initial_balance * max_loss_pct
        
        print(f"   [FINANZAS] Balance Inicial: ${self.initial_balance:.2f} | Límite Pérdida Diaria: -${self.max_daily_loss:.2f}")

    def get_balance_total(self):
        """
        Consulta a Binance el saldo total de la billetera de Futuros (USDT).
        """
        try:
            # Accedemos al cliente de Binance a través del APIManager
            # balance() devuelve una lista de activos
            balances = self.conn.client.balance()
            
            for asset in balances:
                if asset['asset'] == 'USDT':
                    # 'balance' es el saldo total (wallet balance)
                    # 'crossWalletBalance' es el saldo disponible + margen cruzado
                    return float(asset['balance'])
            
            return 0.0
        except Exception as e:
            # Si falla la conexión, retornamos el último conocido o 0
            print(f"⚠️ [FINANZAS] Error leyendo balance: {e}")
            return self.current_balance

    def get_daily_pnl(self):
        """
        Calcula el PnL de la sesión actual (Balance Actual - Balance Inicial).
        Nota: Esto se resetea si reinicias el bot.
        """
        self.current_balance = self.get_balance_total()
        self.daily_pnl = self.current_balance - self.initial_balance
        return self.daily_pnl

    def registrar_pnl(self, amount):
        """
        Método para que el Contralor registre ganancias/pérdidas realizadas manualmente
        si fuera necesario (para logs o métricas internas).
        """
        self.daily_pnl += amount
        # Actualizamos balance teórico
        self.current_balance += amount

    def puedo_operar(self):
        """
        Semáforo de Riesgo Financiero.
        Retorna (True, "") si se puede operar.
        Retorna (False, "Razón") si se bloquea.
        """
        # 1. Verificar si alcanzamos el límite de pérdida diaria
        if self.daily_pnl < -(self.max_daily_loss):
            return False, f"Límite de pérdida diaria alcanzado (${self.daily_pnl:.2f})"

        # 2. Verificar capital mínimo (ej. $10)
        if self.current_balance < 10.0:
            return False, "Capital insuficiente (< $10)"

        return True, "OK"