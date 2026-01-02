# =============================================================================
# UBICACIÓN: simulation/mock_api.py
# DESCRIPCIÓN: MOCK API V4 (STREAMING DISK + INSTANT LIMIT FILL)
# =============================================================================

import uuid
import time
import csv
import os

class MockAPIManager:
    def __init__(self, logger, initial_balance=1000.0, csv_file="simulation_report_v17.csv"):
        self.log = logger
        self.balance_usdt = initial_balance
        self.symbol = "AAVEUSDT"
        self.csv_file = csv_file
        
        # Reiniciar CSV de reporte
        self._init_csv()

        self.current_price = 0.0
        self.current_time = None
        
        # Posiciones (Hedge Mode)
        self.positions = {
            'LONG': {'amount': 0.0, 'entry_price': 0.0, 'unrealized_pnl': 0.0},
            'SHORT': {'amount': 0.0, 'entry_price': 0.0, 'unrealized_pnl': 0.0}
        }
        
        self.open_orders = {}

    def _init_csv(self):
        """Prepara el archivo para escritura inmediata (Streaming)."""
        if os.path.exists(self.csv_file):
            try: os.remove(self.csv_file)
            except: pass
            
        with open(self.csv_file, mode='w', newline='') as f:
            writer = csv.writer(f)
            # Headers del reporte
            writer.writerow(['time', 'symbol', 'type', 'side', 'pos_side', 'price', 'qty', 'fee', 'balance_after'])

    def _write_trade_to_disk(self, record):
        """Escribe una operación al disco inmediatamente."""
        try:
            with open(self.csv_file, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    record['time'], record['symbol'], record['type'], 
                    record['side'], record['pos_side'], record['price'], 
                    record['qty'], record['fee'], self.balance_usdt
                ])
        except Exception as e:
            print(f"⚠️ Error escribiendo CSV: {e}")

    # --- MOTOR DE ESTADO ---

    def update_market_state(self, price, timestamp):
        self.current_price = price
        self.current_time = timestamp
        self._recalc_unrealized_pnl()

    def check_fills(self, high, low):
        """Revisa si las órdenes pendientes (Stops/Limits no llenados) se tocan."""
        filled_ids = []
        
        for oid, order in self.open_orders.items():
            side = order['side'] 
            otype = order['type']
            price_trigger = float(order.get('price', 0) if order.get('price') else order.get('stopPrice', 0))
            
            executed = False
            fill_price = 0.0
            
            # Lógica Standard
            if otype == 'LIMIT':
                if side == 'BUY' and low <= price_trigger:
                    executed = True; fill_price = price_trigger
                elif side == 'SELL' and high >= price_trigger:
                    executed = True; fill_price = price_trigger
            
            elif otype in ['STOP_MARKET', 'STOP']:
                if side == 'SELL' and low <= price_trigger: 
                    executed = True; fill_price = price_trigger 
                elif side == 'BUY' and high >= price_trigger: 
                    executed = True; fill_price = price_trigger
            
            if executed:
                self._execute_trade(order, fill_price)
                filled_ids.append(oid)
        
        for oid in filled_ids:
            del self.open_orders[oid]
        return filled_ids

    def _execute_trade(self, order, price):
        side = order['side'] 
        pos_side = order['positionSide'] 
        
        qty = 0.0
        if 'quantity' in order:
            qty = float(order['quantity'])
        elif order.get('closePosition') == 'true':
            qty = self.positions[pos_side]['amount']
        
        if qty <= 0: return 

        cost = qty * price
        fee = cost * 0.0005 

        self.balance_usdt -= fee 
        
        # LOGICA HEDGE
        p = self.positions[pos_side]
        
        # ABRIR
        if (pos_side == 'LONG' and side == 'BUY') or (pos_side == 'SHORT' and side == 'SELL'):
            new_amt = p['amount'] + qty
            if new_amt > 0:
                total_val = (p['amount'] * p['entry_price']) + (qty * price)
                p['entry_price'] = total_val / new_amt
            p['amount'] = new_amt

        # CERRAR
        else:
            if pos_side == 'LONG': pnl = (price - p['entry_price']) * qty
            else: pnl = (p['entry_price'] - price) * qty
            
            self.balance_usdt += pnl
            p['amount'] = max(0.0, p['amount'] - qty)
            if p['amount'] < 1e-9: 
                p['amount'] = 0.0; p['entry_price'] = 0.0

        # STREAMING AL DISCO
        self._write_trade_to_disk({
            'time': self.current_time, 'symbol': order['symbol'],
            'type': order['type'], 'side': side, 'pos_side': pos_side,
            'price': price, 'qty': qty, 'fee': fee
        })

    def _recalc_unrealized_pnl(self):
        pl = self.positions['LONG']
        pl['unrealized_pnl'] = (self.current_price - pl['entry_price']) * pl['amount'] if pl['amount'] > 0 else 0.0
        ps = self.positions['SHORT']
        ps['unrealized_pnl'] = (ps['entry_price'] - self.current_price) * ps['amount'] if ps['amount'] > 0 else 0.0

    # --- INTERFAZ BINANCE ---

    @property
    def client(self): return self 
    
    def balance(self): 
        return [{'asset': 'USDT', 'balance': self.balance_usdt, 'withdrawAvailable': self.balance_usdt, 'crossWalletBalance': self.balance_usdt}]
    
    def get_ticker_price(self, symbol): return self.current_price
    def get_account_balance(self): return self.balance_usdt
    def get_balance_total(self): return self.balance_usdt
    
    def get_position_info(self, symbol):
        res = []
        for side in ['LONG', 'SHORT']:
            p = self.positions[side]
            res.append({'symbol': symbol, 'positionSide': side, 'positionAmt': p['amount'] if side == 'LONG' else -p['amount'], 'entryPrice': p['entry_price'], 'unRealizedProfit': p['unrealized_pnl'], 'leverage': 5, 'marginType': 'isolated'})
        return res
        
    def get_open_orders(self, symbol):
        res = []
        for oid, o in self.open_orders.items():
            res.append({'orderId': oid, 'symbol': o['symbol'], 'side': o['side'], 'type': o['type'], 'price': o.get('price', 0), 'stopPrice': o.get('stopPrice', 0), 'origQty': o.get('quantity', 0), 'positionSide': o['positionSide'], 'status': 'NEW'})
        return res

    def execute_generic_order(self, params):
        oid = str(int(uuid.uuid4().int))[:10]
        params['orderId'] = oid
        
        # 1. MARKET ORDER
        if params['type'] == 'MARKET':
            self._execute_trade(params, self.current_price)
            params['status'] = 'FILLED'; params['avgPrice'] = self.current_price; params['executedQty'] = params.get('quantity', 0)
            return True, params
            
        # 2. LIMIT ORDER (FIX SHADOW/SWING)
        # Si es LIMIT pero el precio ya es alcanzable (Marketable), llenamos YA.
        elif params['type'] == 'LIMIT':
            price = float(params['price'])
            side = params['side']
            # Compra Limit >= Precio Actual O Venta Limit <= Precio Actual
            is_marketable = (side == 'BUY' and price >= self.current_price) or \
                            (side == 'SELL' and price <= self.current_price)
                            
            if is_marketable:
                # Ejecución Inmediata
                self._execute_trade(params, self.current_price) # Llenamos al precio actual (mejor ejecución)
                params['status'] = 'FILLED'; params['avgPrice'] = self.current_price; params['executedQty'] = params.get('quantity', 0)
                return True, params
            else:
                # Guardar en libro pendiente
                params['status'] = 'NEW'
                self.open_orders[oid] = params
                return True, params

        # 3. STOP ORDERS (Siempre pendientes)
        else:
            params['status'] = 'NEW'
            self.open_orders[oid] = params
            return True, params

    def query_order(self, symbol, orderId):
        # Si está en open_orders es NEW, si no, asumimos FILLED (para el OrderManager)
        return {'status': 'NEW', 'avgPrice': 0.0, 'executedQty': 0.0} if str(orderId) in self.open_orders else {'status': 'FILLED', 'avgPrice': self.current_price, 'executedQty': 0.0}

    def cancel_order(self, symbol, orderId):
        oid = str(orderId)
        if oid in self.open_orders: del self.open_orders[oid]; return True
        return False

    def cancel_all_open_orders(self, symbol): self.open_orders.clear(); return True
    
    # Dummies
    def change_position_mode(self, **kwargs): pass
    def change_margin_type(self, **kwargs): pass
    def change_leverage(self, **kwargs): pass
    def time(self): return int(time.time()*1000)