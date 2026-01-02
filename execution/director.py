# =============================================================================
# UBICACIÓN: execution/director.py
# DESCRIPCIÓN: BINANCE ORDER DIRECTOR (V1.0 - PAYLOAD ARCHITECT)
# =============================================================================

import math

class BinanceOrderDirector:
    """
    DIRECTOR DE ORQUESTACIÓN:
    Traduce intenciones estratégicas (Planes) a sintaxis técnica de Binance.
    Responsabilidades:
    1. Decidir tipo de orden (MARKET vs LIMIT).
    2. Blindar decimales (Precisiones).
    3. Construir payloads correctos para Hedge Mode.
    """
    def __init__(self, config):
        self.cfg = config
        # Cargamos precisiones
        self.qty_prec = getattr(self.cfg, 'QTY_PRECISION', 1)
        self.price_prec = getattr(self.cfg, 'PRICE_PRECISION', 2)

    # =========================================================================
    # 1. CONSTRUCTORES DE ENTRADA (ENTRY)
    # =========================================================================
    
    def construir_entrada(self, plan):
        """
        Decide y construye el payload de entrada.
        Gamma -> Market
        Shadow/Swing -> Limit (por defecto)
        """
        strat = plan.get('strategy', 'UNKNOWN').upper()
        exec_type = plan.get('execution_type', 'AUTO')
        
        # Lógica de decisión
        es_market = False
        
        if exec_type == 'MARKET':
            es_market = True
        elif exec_type == 'LIMIT':
            es_market = False
        else:
            # AUTO: Gamma es Market, resto Limit
            if 'GAMMA' in strat: es_market = True
            else: es_market = False # Shadow y Swing prefieren Limit

        if es_market:
            return self._entry_market(plan)
        else:
            return self._entry_limit(plan)

    def _entry_market(self, plan):
        return {
            'symbol': plan['symbol'],
            'side': 'BUY' if plan['side'] == 'LONG' else 'SELL',
            'positionSide': plan['side'], # OBLIGATORIO HEDGE
            'type': 'MARKET',
            'quantity': self._blindar_qty(plan['qty'])
        }

    def _entry_limit(self, plan):
        return {
            'symbol': plan['symbol'],
            'side': 'BUY' if plan['side'] == 'LONG' else 'SELL',
            'positionSide': plan['side'],
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'quantity': self._blindar_qty(plan['qty']),
            'price': self._blindar_precio(plan['entry_price'])
        }

    # =========================================================================
    # 2. CONSTRUCTORES DE SALIDA / PROTECCIÓN
    # =========================================================================

    def construir_stop_loss(self, symbol, side, price):
        """
        Cierre TOTAL de emergencia (SL).
        Usa 'closePosition=true' -> No requiere cantidad.
        """
        # En Hedge Mode, el SL de un LONG es una orden SELL
        sl_side = 'SELL' if side == 'LONG' else 'BUY'
        
        return {
            'symbol': symbol,
            'side': sl_side,
            'positionSide': side,
            'type': 'STOP_MARKET',
            'stopPrice': self._blindar_precio(price),
            'closePosition': 'true', # Cierra todo limpiamente
            'timeInForce': 'GTC'
        }

    def construir_take_profit_limit(self, symbol, side, qty, price, reduce_only=True):
        """
        Salida PARCIAL o TOTAL (TP).
        Orden LIMIT contraria.
        """
        exit_side = 'SELL' if side == 'LONG' else 'BUY'
        
        payload = {
            'symbol': symbol,
            'side': exit_side,
            'positionSide': side,
            'type': 'LIMIT',
            'quantity': self._blindar_qty(qty),
            'price': self._blindar_precio(price),
            'timeInForce': 'GTC'
        }
        
        if reduce_only:
            payload['reduceOnly'] = 'true'
            
        return payload

    # =========================================================================
    # 3. UTILIDADES DE BLINDAJE
    # =========================================================================
    
    def _blindar_qty(self, qty):
        """Formatea cantidad a string con decimales exactos (Floor)."""
        try:
            factor = 10 ** self.qty_prec
            val = math.floor(float(qty) * factor) / factor
            return "{:.{}f}".format(val, self.qty_prec)
        except: return str(qty)

    def _blindar_precio(self, price):
        """Formatea precio a string."""
        try:
            return "{:.{}f}".format(float(price), self.price_prec)
        except: return str(price)