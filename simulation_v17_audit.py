# =============================================================================
# ARCHIVO: simulation_v18_diagnostic.py
# DESCRIPCIÓN: V18 (INTERCEPTOR DE RAZONES DE CIERRE)
# =============================================================================

import os
import sys
import pandas as pd
import time
import uuid
import csv
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN DE RUTAS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) if 'simulation' in current_dir else current_dir
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, ''))

from config.config import Config
from logic.brain import Brain
from logic.shooter import Shooter
from execution.order_manager import OrderManager
from core.financials import Financials
from execution.comptroller import Comptroller
import execution.order_manager
execution.order_manager.time.sleep = lambda t: None

# =============================================================================
# 🔧 PARCHE DE SEGURIDAD
# =============================================================================
print("🔧 APLICANDO PARCHE: SLOTS = 1")
Config.MAX_GAMMA_SLOTS = 1
Config.MAX_SWING_SLOTS = 1
Config.MAX_SHADOW_SLOTS = 1

# =============================================================================
# 📂 CARGADOR DE DATOS INYECTADO
# =============================================================================
def cargar_datos_robusto():
    print("📂 Cargando datos...")
    base_dir = os.path.abspath(os.getcwd())
    data_dir = os.path.join(base_dir, "data", "historical")
    if not os.path.exists(data_dir):
        base_dir = os.path.dirname(base_dir)
        data_dir = os.path.join(base_dir, "data", "historical")

    symbol = Config.SYMBOL 
    files_map = {f"{symbol}_1m.csv": "1m", f"{symbol}_5m.csv": "5m", f"{symbol}_15m.csv": "15m", f"{symbol}_1h.csv": "1h", f"{symbol}_4h.csv": "4h"}
    cache = {}
    
    for filename, tf_key in files_map.items():
        file_path = os.path.join(data_dir, filename)
        if not os.path.exists(file_path): continue
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.strip().lower() for c in df.columns]
            if 'timestamp' in df.columns:
                if df['timestamp'].iloc[0] > 10000000000: df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                else: df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                df.set_index('timestamp', inplace=True)
            elif 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            cache[tf_key] = df
        except: pass
    return cache

# =============================================================================
# 2. MOCK API V18 (CON SIGNOS CORRECTOS)
# =============================================================================
class MockAPI_V18:
    def __init__(self):
        self.current_price = 0.0
        self.current_ts = None
        self.positions = {} 
        self.orders = {}
        self.client = self 

    def update_market(self, price, timestamp):
        self.current_price = price
        self.current_ts = timestamp
        self._check_orders()

    def _check_orders(self):
        for oid, order in list(self.orders.items()):
            if order['status'] != 'NEW': continue
            
            # Bloqueo de seguridad: No ejecutar en el mismo minuto de creación
            if order.get('creation_ts') == self.current_ts: continue

            side = order['side']
            otype = order['type']
            trigger = float(order.get('price', 0) or order.get('stopPrice', 0))
            
            fill = False
            if otype == 'LIMIT':
                if (side == 'BUY' and self.current_price <= trigger) or (side == 'SELL' and self.current_price >= trigger): fill = True
            elif otype == 'STOP_MARKET':
                if (side == 'SELL' and self.current_price <= trigger) or (side == 'BUY' and self.current_price >= trigger): fill = True
                
            if fill:
                order['status'] = 'FILLED'
                order['avgPrice'] = self.current_price 
                if otype == 'LIMIT': order['avgPrice'] = trigger
                
                if str(order.get('closePosition')).lower() == 'true':
                    pos_side = order['positionSide']
                    key = f"{order['symbol']}_{pos_side}"
                    if key in self.positions:
                        order['executedQty'] = self.positions[key]['positionAmt']
                else:
                    order['executedQty'] = order['origQty']

                self._update_position_internal(order)

    def _update_position_internal(self, order):
        symbol = order['symbol']
        side = order['positionSide']
        qty = float(order['executedQty'])
        price = float(order['avgPrice'])
        
        key = f"{symbol}_{side}"
        if key not in self.positions:
            self.positions[key] = {
                'symbol': symbol, 'positionSide': side, 'positionAmt': 0.0,
                'entryPrice': 0.0, 'unRealizedProfit': 0.0
            }
        pos = self.positions[key]
        curr_amt = float(pos['positionAmt'])
        
        if order['side'] == 'BUY':
            if side == 'LONG': 
                total_cost = (curr_amt * float(pos['entryPrice'])) + (qty * price)
                new_amt = curr_amt + qty
                pos['entryPrice'] = total_cost / new_amt if new_amt > 0 else 0
                pos['positionAmt'] = new_amt
            else: 
                pos['positionAmt'] = max(0, curr_amt - qty)
        else: 
            if side == 'SHORT': 
                total_cost = (curr_amt * float(pos['entryPrice'])) + (qty * price)
                new_amt = curr_amt + qty
                pos['entryPrice'] = total_cost / new_amt if new_amt > 0 else 0
                pos['positionAmt'] = new_amt
            else: 
                pos['positionAmt'] = max(0, curr_amt - qty)

    # API Methods
    def place_market_order(self, symbol, side, quantity, position_side=None, reduce_only=False):
        params = {'symbol': symbol, 'side': side, 'type': 'MARKET', 'quantity': quantity, 'positionSide': position_side}
        return self.execute_generic_order(params)[1]

    def get_position_info(self, symbol):
        output = []
        for s in ['LONG', 'SHORT']:
            key = f"{symbol}_{s}"
            if key in self.positions:
                p = self.positions[key].copy()
                amt = float(p['positionAmt'])
                entry = float(p['entryPrice'])
                pnl = 0.0
                if amt > 0:
                    if s == 'LONG': pnl = (self.current_price - entry) * amt
                    else: 
                        pnl = (entry - self.current_price) * amt
                        amt = -amt 
                
                p['positionAmt'] = str(amt) 
                p['entryPrice'] = str(entry)
                p['unRealizedProfit'] = str(pnl)
                p['leverage'] = '5'
                output.append(p)
            else:
                output.append({
                    'symbol': symbol, 'positionSide': s, 
                    'positionAmt': '0.0', 'entryPrice': '0.0', 
                    'unRealizedProfit': '0.0', 'leverage': '5'
                })
        return output

    def get_open_orders(self, symbol): return [o for o in self.orders.values() if o['status'] == 'NEW']
    
    def execute_generic_order(self, params):
        oid = str(uuid.uuid4())[:8]
        order = params.copy()
        order['orderId'] = oid
        order['origQty'] = params.get('quantity', 0)
        order['executedQty'] = '0.0'
        order['status'] = 'NEW'
        order['positionSide'] = params.get('positionSide', 'LONG')
        order['creation_ts'] = self.current_ts 
        
        if params['type'] == 'MARKET':
            order['status'] = 'FILLED'
            order['avgPrice'] = self.current_price
            order['executedQty'] = params['quantity']
            self._update_position_internal(order)
            
        self.orders[oid] = order
        return True, order

    def cancel_order(self, symbol, order_id): return True
    def cancel_all_open_orders(self, symbol): return True
    def query_order(self, symbol, orderId): return {'status': 'CANCELED'}
    def exchange_info(self):
        return {'symbols': [{'symbol': Config.SYMBOL, 'filters': [{'filterType': 'LOT_SIZE', 'stepSize': '0.001', 'minQty': '0.001'}, {'filterType': 'PRICE_FILTER', 'tickSize': '0.01'}]}]}

# =============================================================================
# 3. ORDER MANAGER DIAGNOSTIC (EL ESPÍA)
# =============================================================================
class OrderManagerDiagnostic(OrderManager):
    def reducir_posicion(self, symbol, qty, reason):
        # AQUÍ ESTÁ LA CLAVE: Interceptamos la razón
        print(f"\n🛑 DIAGNÓSTICO FINAL: El Comptroller intentó cerrar {qty} uds.")
        print(f"👉 RAZÓN EXACTA RECIBIDA: '{reason}'")
        print("---------------------------------------------------------------")
        return super().reducir_posicion(symbol, qty, reason)

# =============================================================================
# 4. COMPTROLLER PATCHED (Solo PnL Calc, sin bloqueo)
# =============================================================================
class ComptrollerPatched(Comptroller):
    def auditar_posiciones(self, current_price, current_ts): 
        # Forzar cálculo PnL
        for key, pos in self.posiciones_activas.items():
            entry = float(pos.get('entry_price', 0))
            if entry > 0:
                if pos['side'] == 'LONG': pos['pnl_pct'] = (current_price - entry) / entry
                else: pos['pnl_pct'] = (entry - current_price) / entry
            
            if 'pnl_pct' in pos:
                if 'max_pnl' not in pos: pos['max_pnl'] = pos['pnl_pct']
                else: 
                     if pos['pnl_pct'] > pos['max_pnl']: pos['max_pnl'] = pos['pnl_pct']

        super().auditar_posiciones(current_price)
        
        # Shadow Patch
        for k, pos in self.posiciones_activas.items():
            if pos.get('strategy') == 'SHADOW':
                self._gestion_shadow_simulada(pos, current_price)

    def _gestion_shadow_simulada(self, pos, current_price):
        pnl_pct = pos.get('pnl_pct', 0)
        max_pnl = pos.get('max_pnl', 0)
        if max_pnl > 0.01: 
            if pnl_pct < (max_pnl - 0.005) and pnl_pct > 0:
                self.om.reducir_posicion(pos['symbol'], float(pos['qty']), "SHADOW_TRAILING")
        if pnl_pct > 0.015: 
             self.om.reducir_posicion(pos['symbol'], float(pos['qty']), "SHADOW_TARGET")

# =============================================================================
# 5. REPORTER & MAIN
# =============================================================================
class SimReporter:
    def __init__(self): self.trades_count = 0
    def registrar_cierre(self, pos, exit_price, exit_time, reason):
        self.trades_count += 1
    def guardar_csv(self): pass

class DummyLogger:
    def registrar_actividad(self, m, msg): pass
    def registrar_error(self, m, msg, c=False): pass

def main():
    print("🚀 INICIANDO DIAGNÓSTICO QUIRÚRGICO V18...")
    cache = cargar_datos_robusto()
    if not cache or '1m' not in cache: return
    
    df_1m = cache['1m']
    timestamps = df_1m.index
    
    mock_api = MockAPI_V18()
    fin = Financials(Config, mock_api)
    # INYECTAMOS EL ESPÍA
    om = OrderManagerDiagnostic(Config, mock_api, DummyLogger(), fin)
    comp = ComptrollerPatched(Config, om, fin, DummyLogger())
    brain = Brain(Config)
    shooter = Shooter(om, fin)
    reporter = SimReporter()
    
    sliced_cache = {tf: df.iloc[:0] for tf, df in cache.items()}
    
    print(f"⚡ Corriendo hasta encontrar el primer cierre...")
    
    WINDOW_SIZE = 500
    
    for i, ts in enumerate(timestamps):
        if i < 300: continue 
        
        row = df_1m.iloc[i]
        price = row['close']
        mock_api.update_market(price, ts) 
        
        if i % 5 == 0:
            for tf in ['15m', '1h', '4h']: 
                if tf in cache: 
                    sub = cache[tf].loc[:ts]
                    sliced_cache[tf] = sub.iloc[-WINDOW_SIZE:] if len(sub) > WINDOW_SIZE else sub
        
        sub_1m = cache['1m'].loc[:ts]
        sliced_cache['1m'] = sub_1m.iloc[-WINDOW_SIZE:] if len(sub_1m) > WINDOW_SIZE else sub_1m
        
        comp.auditar_posiciones(price, ts)
        
        # 2. Entrada
        signals = brain.analizar_mercado(sliced_cache)
        if signals:
            if not isinstance(signals, list): signals = [signals]
            for sig in signals:
                plan = shooter.validar_y_crear_plan(sig, comp.posiciones_activas)
                if plan:
                    plan['id'] = str(uuid.uuid4())[:8]
                    plan['timestamp'] = ts
                    ok, pkg = om.ejecutar_estrategia(plan)
                    if ok:
                        # Forzamos la entrada del Timestamp para que el Comptroller lo tenga
                        pkg['timestamp'] = ts 
                        comp.aceptar_custodia(pkg)
                        print(f"🟢 ENTRADA: {sig['strategy']} {sig['signal']} @ {price}")

        # 3. Detectar cierre por OrderManager (El Espía lo imprimirá)
        # Si detectamos cierres, paramos para que el usuario lea.
        if reporter.trades_count > 3: # Dejar pasar unos pocos
             print("\n⚠️ ALTO: Suficientes muestras recolectadas.")
             return

        # Chequeo manual si se cerró algo
        for k, pos in list(comp.posiciones_activas.items()):
            if pos.get('qty', 0) == 0:
                 reporter.registrar_cierre(pos, price, ts, "LOGIC_CLOSE")
                 del comp.posiciones_activas[k]

if __name__ == "__main__":
    main()