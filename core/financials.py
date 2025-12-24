<<<<<<< HEAD
=======
# =============================================================================
# UBICACIÓN: core/financials.py
# DESCRIPCIÓN: GESTOR FINANCIERO (RESTAURADO V13 COMPATIBLE)
# =============================================================================

>>>>>>> 4c4d97b (commit 24/12)
from binance.error import ClientError

class Financials:
    """
<<<<<<< HEAD
    DEPARTAMENTO FINANCIERO (V13.6 - RECOVERY FIX):
    Permite al bot ver las posiciones reales en Binance para no duplicar órdenes.
=======
    DEPARTAMENTO FINANCIERO:
    Encargado de leer Balances y Posiciones.
    Restaurado a la lógica original de V13.6 que funcionaba correctamente.
>>>>>>> 4c4d97b (commit 24/12)
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
<<<<<<< HEAD
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
=======
        Retorna el saldo disponible en USDT.
        Usa el método .balance() que es compatible con tu versión de cliente.
        """
        try:
            # RETORNO A LÓGICA ORIGINAL
            balances = self.api.client.balance()
            
            # Validación de seguridad básica
            if not balances:
                return 0.0

            for b in balances:
                if b['asset'] == 'USDT':
                    return float(b['balance']) 
            return 0.0
            
        except Exception:
            # Retornar 0 en silencio para no romper el bucle visual
            return 0.0

    def obtener_posiciones_activas_simple(self):
        """
        Consulta posiciones reales abiertas.
        Mantiene la estructura original que alimentaba correctamente al Dashboard.
        """
        try:
            # Llamada original
            raw_pos = self.api.get_position_info(self.cfg.SYMBOL)
            
            if raw_pos is None: return []

            activas = []
            # Normalización segura (lista o dict)
            lista_raw = raw_pos if isinstance(raw_pos, list) else [raw_pos]
            
            for p in lista_raw:
                # Usamos .get() por seguridad, pero mantenemos las claves originales
                amt = float(p.get('positionAmt', 0))
                
                if amt != 0:
                    side = 'LONG' if amt > 0 else 'SHORT'
                    
                    activas.append({
                        'symbol': p.get('symbol'),
                        'side': side,
                        'qty': abs(amt),
                        'entry_price': float(p.get('entryPrice', 0)),
                        'pnl': float(p.get('unRealizedProfit', 0)),
                        # Mantenemos solo los datos que el dashboard V8.4 sabe leer
                    })
            return activas
            
        except Exception as e:
            print(f"⚠️ Error en Financials: {e}")
>>>>>>> 4c4d97b (commit 24/12)
            return []