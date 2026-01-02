# =============================================================================
# UBICACIÓN: core/financials.py
# DESCRIPCIÓN: GESTOR FINANCIERO V17.6 (SYNC SAFEGUARD)
# =============================================================================

class Financials:
    """
    DEPARTAMENTO FINANCIERO V17.6:
    - Protege el Libro Local contra fallos de lectura de la API.
    - Si la API falla, confiamos en el OrderManager.
    """
    def __init__(self, config, api_manager):
        self.cfg = config
        self.api = api_manager
        self.libro_ordenes_local = {} 

    # =========================================================================
    # GESTIÓN DEL LIBRO LOCAL
    # =========================================================================
    
    def registrar_orden_en_libro(self, order_data):
        oid = str(order_data['orderId'])
        self.libro_ordenes_local[oid] = order_data

    def eliminar_orden_del_libro(self, order_id):
        oid = str(order_id)
        if oid in self.libro_ordenes_local:
            del self.libro_ordenes_local[oid]

    def sincronizar_libro_con_api(self):
        """
        Intenta descargar la verdad de Binance.
        CRÍTICO: Si la API falla (None), NO borramos el libro local.
        """
        try:
            raw_orders = self.api.get_open_orders(self.cfg.SYMBOL)
            
            # 🛑 SALVAGUARDA: Si recibimos None, la API falló. Abortamos sync.
            if raw_orders is None:
                # print("⚠️ Sync omitido: API error (Usando memoria local)")
                return False

            # Si llegamos aquí, la lectura fue exitosa (aunque sea lista vacía [])
            nuevo_libro = {}
            for o in raw_orders:
                nuevo_libro[str(o['orderId'])] = o
            
            self.libro_ordenes_local = nuevo_libro
            return True
            
        except Exception:
            return False

    def verificar_si_tiene_sl_local(self, side_posicion):
        target_side = 'SELL' if side_posicion == 'LONG' else 'BUY'
        tipos_sl = ['STOP_MARKET', 'STOP', 'TRAILING_STOP_MARKET']
        
        for oid, order in self.libro_ordenes_local.items():
            if order['side'] == target_side and order['type'] in tipos_sl:
                if order.get('positionSide') == side_posicion:
                    price = float(order.get('stopPrice', 0) or order.get('activationPrice', 0))
                    return True, price, oid
        return False, 0.0, None

    # =========================================================================
    # LECTURAS
    # =========================================================================

    def get_balance_total(self):
        try:
            balances = self.api.client.balance()
            for b in balances:
                if b['asset'] == 'USDT': return float(b['balance']) 
            return 0.0
        except: return 0.0

    def obtener_posiciones_activas_simple(self):
        try:
            raw_pos = self.api.get_position_info(self.cfg.SYMBOL)
            if raw_pos is None: return [] # Null safety
            
            activas = []
            lista_raw = raw_pos if isinstance(raw_pos, list) else [raw_pos]
            
            for p in lista_raw:
                if p is None: continue
                amt = float(p.get('positionAmt', 0))
                if amt != 0:
                    side = 'LONG' if amt > 0 else 'SHORT'
                    activas.append({
                        'symbol': p['symbol'],
                        'side': side,
                        'qty': abs(amt),
                        'entry_price': float(p['entryPrice']),
                        'pnl': float(p['unRealizedProfit']),
                        'leverage': int(p.get('leverage', 1))
                    })
            return activas
        except: return []