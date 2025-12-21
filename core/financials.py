from binance.error import ClientError

class Financials:
    """
    DEPARTAMENTO FINANCIERO (V13.6 - RECOVERY FIX):
    Permite al bot ver las posiciones reales en Binance para no duplicar órdenes.
    """
    def __init__(self, config, api_manager):
        self.cfg = config
        self.api = api_manager

    def get_balance_total(self):
        """Retorna el saldo disponible en USDT."""
        try:
            balances = self.api.client.balance()
            for b in balances:
                if b['asset'] == 'USDT':
                    return float(b['balance']) 
            return 0.0
        except Exception:
            return 0.0

    def obtener_posiciones_activas_simple(self):
        """
        MÉTODO CRÍTICO: Consulta a Binance qué tenemos abierto realmente.
        """
        try:
            # Obtenemos info cruda del API Manager
            raw_pos = self.api.get_position_info(self.cfg.SYMBOL)
            activas = []
            
            # Normalizamos a lista
            lista_raw = raw_pos if isinstance(raw_pos, list) else [raw_pos]
            
            for p in lista_raw:
                amt = float(p['positionAmt'])
                if amt != 0:
                    # Detectamos si es LONG o SHORT
                    side = 'LONG' if amt > 0 else 'SHORT'
                    
                    activas.append({
                        'symbol': p['symbol'],
                        'side': side,
                        'qty': abs(amt),
                        'entry_price': float(p['entryPrice']),
                        'pnl': float(p['unRealizedProfit'])
                    })
            return activas
            
        except Exception as e:
            print(f"⚠️ Error crítico en Financials: {e}")
            return []