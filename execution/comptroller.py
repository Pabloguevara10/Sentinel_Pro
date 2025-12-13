import csv
import os
from config.config import Config

class Comptroller:
    """
    DEPARTAMENTO DE CONTROL INTERNO (Contralor):
    Custodia las posiciones abiertas. Gestiona Break Even, Trailing Stop.
    VERSION: 8.3 (Soporte persistencia SL_ORDER_ID y Fix closePosition)
    """
    def __init__(self, config, order_manager, financials, logger):
        self.cfg = config
        self.om = order_manager
        self.fin = financials 
        self.log = logger
        
        self.posiciones_activas = {} 
        self._recuperar_estado_de_bitacora()

    def aceptar_custodia(self, paquete_posicion):
        pid = paquete_posicion['id']
        paquete_posicion['be_activado'] = False  
        paquete_posicion['ts_activado'] = False  
        paquete_posicion['tp_alcanzados'] = 0    
        
        self.posiciones_activas[pid] = paquete_posicion
        self.log.registrar_actividad("CONTRALOR", f"🔒 Posición {pid} bajo custodia.")

    def auditar_posiciones(self, current_price):
        if not self.posiciones_activas:
            return

        for pid, pos in list(self.posiciones_activas.items()):
            side = pos['side'] 
            entry = pos['entry_price']
            
            if side == 'LONG':
                roi_pct = (current_price - entry) / entry
            else: 
                roi_pct = (entry - current_price) / entry
                
            # Regla: Break Even al 1%
            if not pos['be_activado'] and roi_pct >= 0.01:
                self._activar_breakeven(pid, pos)

            # Regla: Trailing Stop al 2%
            if roi_pct >= 0.02:
                self._gestionar_trailing(pid, pos, current_price, roi_pct)

    def _activar_breakeven(self, pid, pos):
        new_sl = pos['entry_price']
        
        # Solo intentamos cancelar si tenemos un ID válido
        if pos['sl_order_id'] and pos['sl_order_id'] != 'UNKNOWN_ON_RESTART':
            self.om.cancelar_orden(pos['sl_order_id'])
        else:
            self.log.registrar_actividad("CONTRALOR", f"⚠️ No se pudo cancelar SL anterior (ID Desconocido). Creando nuevo B/E.")
        
        sl_side = 'SELL' if pos['side'] == 'LONG' else 'BUY'
        
        # FIX: No enviar quantity con closePosition=true
        params_sl = {
            'symbol': self.cfg.SYMBOL,
            'side': sl_side,
            'type': 'STOP_MARKET',
            'stopPrice': new_sl,
            'positionSide': pos['side'],
            'timeInForce': 'GTC',
            'closePosition': 'true'
        }
        res = self.om.conn.place_order(params_sl)
        
        if res and 'orderId' in res:
            pos['sl_order_id'] = res['orderId']
            pos['sl_price'] = new_sl
            pos['be_activado'] = True
            self.log.registrar_actividad("CONTRALOR", f"🛡️ B/E Activado para {pid}. SL movido a entrada.")

    def _gestionar_trailing(self, pid, pos, current_price, roi_pct):
        distancia = 0.01
        new_sl = 0.0
        
        if pos['side'] == 'LONG':
            possible_sl = current_price * (1 - distancia)
            if possible_sl > pos['sl_price']:
                new_sl = possible_sl
        else: 
            possible_sl = current_price * (1 + distancia)
            if possible_sl < pos['sl_price']:
                new_sl = possible_sl
        
        if new_sl != 0.0:
            diff = abs(new_sl - pos['sl_price']) / pos['sl_price']
            if diff > 0.002:
                # Cancelar viejo
                if pos['sl_order_id'] and pos['sl_order_id'] != 'UNKNOWN_ON_RESTART':
                    self.om.cancelar_orden(pos['sl_order_id'])
                
                sl_side = 'SELL' if pos['side'] == 'LONG' else 'BUY'
                
                # FIX: No enviar quantity
                params_sl = {
                    'symbol': self.cfg.SYMBOL,
                    'side': sl_side,
                    'type': 'STOP_MARKET',
                    'stopPrice': round(new_sl, 2),
                    'positionSide': pos['side'],
                    'closePosition': 'true'
                }
                res = self.om.conn.place_order(params_sl)
                if res and 'orderId' in res:
                    pos['sl_order_id'] = res['orderId']
                    pos['sl_price'] = new_sl
                    pos['ts_activado'] = True
                    self.log.registrar_actividad("CONTRALOR", f"🚀 Trailing Stop actualizado para {pid} a {new_sl:.2f}")

    def _recuperar_estado_de_bitacora(self):
        if not os.path.exists(self.cfg.FILE_LOG_ORDERS):
            return

        try:
            with open(self.cfg.FILE_LOG_ORDERS, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['ESTADO'] == 'ABIERTA':
                        self.log.registrar_actividad("CONTRALOR", f"♻️ Recuperando posición {row['ID_POSICION']} de la memoria.")
                        
                        # Intentar leer SL_ORDER_ID, si no existe (CSV viejo) usar marca
                        sl_id = row.get('SL_ORDER_ID', 'UNKNOWN_ON_RESTART')
                        
                        pos = {
                            'id': row['ID_POSICION'],
                            'side': row['SIDE'],
                            'entry_price': float(row['PRECIO_ENTRADA']),
                            'qty': float(row['QTY']),
                            'sl_price': float(row['SL_PRICE']),
                            'sl_order_id': sl_id,
                            'be_activado': False,
                            'ts_activado': False
                        }
                        self.posiciones_activas[pos['id']] = pos
                        
        except Exception as e:
            self.log.registrar_error("CONTRALOR", f"Error recuperando estado: {e}")

    def get_open_positions_count(self):
        return len(self.posiciones_activas)