# =============================================================================
# UBICACIÓN: simulation/mock_api.py
# DESCRIPCIÓN: MOCK API V9 (FULL COMPATIBLE: CANCEL & GENERIC ORDERS)
# =============================================================================

import uuid
import time
import csv
import os
import random

class MockAPIManager:
    def __init__(self, logger, initial_balance=1000.0, csv_file="simulation_report_v17.csv", stress_mode=False):
        self.log = logger
        self.balance_usdt = initial_balance
        self.symbol = "AAVEUSDT"
        self.csv_file = csv_file
        self.stress_mode = stress_mode
        
        # TRUCO DE COMPATIBILIDAD:
        # Redirigimos .client a self para que las llamadas tipo api.client.x() funcionen
        self.client = self 

        self._init_csv()

        self.current_price = 0.0
        self.current_time = None
        
        self.positions = {
            'LONG': {'amount': 0.0, 'entry_price': 0.0, 'unrealized_pnl': 0.0},
            'SHORT': {'amount': 0.0, 'entry_price': 0.0, 'unrealized_pnl': 0.0}
        }
        
        self.open_orders = {}

    def _init_csv(self):
        if os.path.exists(self.csv_file):
            try: os.remove(self.csv_file)
            except: pass
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Event', 'Side', 'Price', 'Qty', 'Balance', 'Comment'])

    def update_market_price(self, price, timestamp):
        self.current_price = price
        self.current_time = timestamp
        self._check_pending_orders()

    # --- LÓGICA DE ESTRÉS (Slippage) ---
    def _apply_stress(self, price, side):
        if not self.stress_mode: return price
        slippage = random.uniform(0.0002, 0.0010) # 0.02% a 0.1%
        if side == 'BUY': return price * (1 + slippage)
        else: return price * (1 - slippage)

    # --- MÉTODOS DE COMPATIBILIDAD CON LIBRERÍA BINANCE ---

    def exchange_info(self):
        return {
            'symbols': [{
                'symbol': self.symbol,
                'quantityPrecision': 3,
                'pricePrecision': 2,
                'filters': [{'filterType': 'LOT_SIZE', 'minQty': '0.1'}]
            }]
        }

    def balance(self):
        return [{'asset': 'USDT', 'balance': str(self.balance_usdt)}]

    def get_position_info(self, symbol=None):
        return [
            {'symbol': self.symbol, 'positionAmt': self.positions['LONG']['amount'], 'entryPrice': self.positions['LONG']['entry_price'], 'side': 'LONG', 'unRealizedProfit': 0.0, 'leverage': 20},
            {'symbol': self.symbol, 'positionAmt': -self.positions['SHORT']['amount'], 'entryPrice': self.positions['SHORT']['entry_price'], 'side': 'SHORT', 'unRealizedProfit': 0.0, 'leverage': 20}
        ]
    
    # --- MÉTODOS DE EJECUCIÓN DEL ORDER MANAGER ---

    def execute_generic_order(self, params):
        return self.place_order(params)

    def place_market_order(self, symbol, side, qty, position_side=None, reduce_only=False):
        params = {'symbol': symbol, 'side': side, 'type': 'MARKET', 'quantity': qty}
        return self.place_order(params)

    def cancel_all_open_orders(self, symbol):
        """Método crítico para cierres de emergencia."""
        self.open_orders.clear()
        return True

    def get_open_orders(self, symbol=None):
        return list(self.open_orders.values())

    # --- GESTIÓN INTERNA DE ÓRDENES ---

    def place_order(self, params):
        order_type = params.get('type', 'MARKET')
        side = params.get('side')
        qty = float(params.get('quantity', 0))
        price = float(params.get('price', self.current_price))
        order_id = str(uuid.uuid4())[:8]
        params['orderId'] = order_id
        params['symbol'] = self.symbol
        
        if order_type == 'MARKET':
            exec_price = self._apply_stress(self.current_price, side)
            self._execute_trade(side, qty, exec_price, "MARKET_FILL")
            params['status'] = 'FILLED'
            params['avgPrice'] = exec_price
            params['executedQty'] = qty
            return True, params

        elif order_type == 'LIMIT':
            can_fill = False
            if side == 'BUY' and self.current_price <= price: can_fill = True
            elif side == 'SELL' and self.current_price >= price: can_fill = True
            
            if can_fill:
                self._execute_trade(side, qty, price, "LIMIT_INSTANT")
                params['status'] = 'FILLED'
                params['avgPrice'] = price
                params['executedQty'] = qty
            else:
                params['status'] = 'NEW'
                self.open_orders[order_id] = params
            
            return True, params
            
        return False, {"msg": "Order type not supported"}

    def _execute_trade(self, side, qty, price, note=""):
        cost = qty * price
        fee = cost * 0.0005
        self.balance_usdt -= fee
        
        if side == 'BUY':
            if self.positions['SHORT']['amount'] > 0:
                self.positions['SHORT']['amount'] -= qty
                if self.positions['SHORT']['amount'] < 0: self.positions['SHORT']['amount'] = 0
            else:
                self.positions['LONG']['amount'] += qty
                self.positions['LONG']['entry_price'] = price 
        elif side == 'SELL':
            if self.positions['LONG']['amount'] > 0:
                self.positions['LONG']['amount'] -= qty
                if self.positions['LONG']['amount'] < 0: self.positions['LONG']['amount'] = 0
            else:
                self.positions['SHORT']['amount'] += qty
                self.positions['SHORT']['entry_price'] = price

        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([self.current_time, 'TRADE', side, f"{price:.2f}", qty, f"{self.balance_usdt:.2f}", note])

    def _check_pending_orders(self):
        filled = []
        for oid, order in self.open_orders.items():
            side = order['side']
            price = float(order['price'])
            qty = float(order['quantity'])
            
            fill = False
            if side == 'BUY' and self.current_price <= price: fill = True
            elif side == 'SELL' and self.current_price >= price: fill = True
            
            if fill:
                self._execute_trade(side, qty, price, "LIMIT_FILL")
                filled.append(oid)
        for oid in filled: del self.open_orders[oid]

    def query_order(self, symbol, orderId):
        oid = str(orderId)
        if oid in self.open_orders:
             return {'status': 'NEW', 'avgPrice': 0.0, 'executedQty': 0.0}
        return {'status': 'FILLED', 'avgPrice': self.current_price, 'executedQty': 0.0}

    def cancel_order(self, symbol, orderId):
        oid = str(orderId)
        if oid in self.open_orders: del self.open_orders[oid]; return True
        return False