# =============================================================================
# UBICACIÓN: execution/comptroller.py
# DESCRIPCIÓN: Contralor Híbrido V15 (Seguridad Total + Tríada)
# =============================================================================

from config.config import Config
from logs.system_logger import SystemLogger

class Comptroller:
    def __init__(self, order_manager, financials):
        self.cfg = Config
        self.om = order_manager
        self.fin = financials
        self.log = SystemLogger()
        self.posiciones_activas = {} 

    def aceptar_custodia(self, paquete_orden):
        """Registra orden en memoria y setea flags iniciales."""
        symbol = paquete_orden['symbol']
        paquete_orden['tp1_hit'] = False
        paquete_orden['tp2_hit'] = False
        paquete_orden['max_price'] = paquete_orden['entry_price']
        
        # ID Único para evitar sobreescritura si hay hedging/cascada
        pid = paquete_orden.get('id')
        if not pid:
            import time
            pid = f"{symbol}_{int(time.time()*1000)}"
            paquete_orden['id'] = pid
            
        self.posiciones_activas[pid] = paquete_orden
        self.log.log_info(f"🛡️ Custodia iniciada: {symbol} ({paquete_orden['strategy']})")

    def auditar_posiciones(self, current_price):
        """Loop principal de auditoría."""
        if not self.posiciones_activas: return

        for pid, pos in list(self.posiciones_activas.items()):
            try:
                # Actualizar High Watermark
                if pos['side'] == 'LONG':
                    if current_price > pos['max_price']: pos['max_price'] = current_price
                    pnl_pct = (current_price - pos['entry_price']) / pos['entry_price']
                else:
                    if current_price < pos['max_price']: pos['max_price'] = current_price
                    pnl_pct = (pos['entry_price'] - current_price) / pos['entry_price']
                
                pos['current_price'] = current_price
                pos['pnl_pct'] = pnl_pct
                
                # Router
                mgmt = pos.get('management_type', 'STATIC')
                
                if mgmt == 'DYNAMIC_TRAILING': # Gamma
                    self._gestion_dynamic_trailing(pos, current_price)
                elif mgmt == 'FRACTIONAL_SWING': # Swing
                    self._gestion_fractional_swing(pos, current_price, pnl_pct)
                elif mgmt == 'SHADOW_CASCADING': # Shadow
                    self._gestion_shadow(pos, current_price, pnl_pct)
                elif mgmt == 'ADOPTED_RECOVERY': # Huérfanas
                    self._gestion_dynamic_trailing(pos, current_price)

            except Exception as e:
                self.log.log_error(f"Error auditando {pid}: {e}")

    # --- LÓGICA DE GESTIÓN ---

    def _gestion_shadow(self, pos, curr, pnl_pct):
        """Shadow: Cierra si el trailing se activa."""
        # Pico máximo relativo
        entry = pos['entry_price']
        peak = pos['max_price']
        
        if pos['side'] == 'LONG': max_gain = (peak - entry)/entry
        else: max_gain = (entry - peak)/entry
        
        # Trailing
        if max_gain > 0.01: # 1% profit min
            trail_dist = self.cfg.SH_TRAILING_PCT # 0.05
            if (max_gain - pnl_pct) > trail_dist:
                self.log.log_info(f"👻 Shadow Trailing: Cerrando {pos['symbol']} @ {curr}")
                self.om.close_position(pos['symbol'], "SHADOW_TRAIL")
                del self.posiciones_activas[pos['id']]

    def _gestion_dynamic_trailing(self, pos, curr):
        """Gamma: Mueve el SL."""
        if float(pos.get('sl_price', 0)) <= 0: return # Seguridad

        # Trailing Distancia
        dist = self.cfg.G_TRAIL_NORM # Usar config general o específica del trade
        
        new_sl = 0.0
        if pos['side'] == 'LONG':
            propuesto = curr * (1 - dist)
            if propuesto > pos['sl_price']: new_sl = propuesto
        else:
            propuesto = curr * (1 + dist)
            if propuesto < pos['sl_price']: new_sl = propuesto
            
        if new_sl > 0:
            # Filtro de spam (0.1% cambio mínimo)
            if abs(new_sl - pos['sl_price']) / pos['sl_price'] > 0.001:
                if self.om.update_stop_loss(pos['symbol'], pos['side'], new_sl, pos['qty']):
                    pos['sl_price'] = new_sl

    def _gestion_fractional_swing(self, pos, curr, pnl_pct):
        """Swing: Parciales."""
        tp1_dist = pos.get('tp1_dist', 0.06)
        tp2_dist = pos.get('tp2_dist', 0.12)
        
        # TP1
        if not pos['tp1_hit'] and pnl_pct >= tp1_dist:
            qty_close = pos['qty'] * pos.get('tp1_qty', 0.3)
            self.log.log_info(f"⭐ Swing TP1: Cerrando parcial {qty_close}")
            # Asumimos que OM tiene close_partial o similar, o usamos close_position con qty
            self.om.close_position(pos['symbol'], "SWING_TP1", qty=qty_close)
            pos['qty'] -= qty_close
            pos['tp1_hit'] = True
            
            # Mover a BE
            self.om.update_stop_loss(pos['symbol'], pos['side'], pos['entry_price'], pos['qty'])
            pos['sl_price'] = pos['entry_price']

        # TP2
        elif not pos['tp2_hit'] and pnl_pct >= tp2_dist:
            qty_close = pos['qty'] * pos.get('tp2_qty', 0.3)
            self.log.log_info(f"🌟 Swing TP2: Cerrando parcial {qty_close}")
            self.om.close_position(pos['symbol'], "SWING_TP2", qty=qty_close)
            pos['qty'] -= qty_close
            pos['tp2_hit'] = True
            # Mover SL a TP1
            new_sl = pos['entry_price'] * (1 + tp1_dist) if pos['side']=='LONG' else pos['entry_price'] * (1 - tp1_dist)
            self.om.update_stop_loss(pos['symbol'], pos['side'], new_sl, pos['qty'])
            pos['sl_price'] = new_sl

    def sincronizar_con_exchange(self):
        """
        Recuperación y Adopción (Restaurada).
        """
        try:
            # 1. Obtener posiciones reales
            real_positions = self.fin.obtener_posiciones_activas_simple()
            if not real_positions: 
                self.posiciones_activas = {}
                return

            real_ids = []
            
            # 2. Adoptar Huérfanos
            for rp in real_positions:
                sym = rp['symbol']
                # Simplificación: Usamos simbolo como ID para recuperación simple
                # Si hay múltiples posiciones del mismo símbolo en modo Hedge, requeriría lógica extra
                pid_match = None
                for pid, mp in self.posiciones_activas.items():
                    if mp['symbol'] == sym and mp['side'] == rp['side']:
                        pid_match = pid
                        break
                
                if not pid_match:
                    self.log.log_warn(f"🕵️ Adoptando posición huérfana: {sym}")
                    # Verificar SL (Lógica simplificada, idealmente consultar Open Orders)
                    # Por defecto, asumimos que necesita protección
                    self._crear_sl_emergencia(rp)
                    
                    # Registrar
                    new_pid = f"REC_{sym}"
                    self.posiciones_activas[new_pid] = {
                        'id': new_pid,
                        'symbol': sym,
                        'side': rp['side'],
                        'qty': rp['qty'],
                        'entry_price': rp['entry_price'],
                        'max_price': rp['entry_price'],
                        'management_type': 'ADOPTED_RECOVERY',
                        'strategy': 'UNKNOWN',
                        'tp1_hit': False, 'tp2_hit': False
                    }
                    real_ids.append(new_pid)
                else:
                    real_ids.append(pid_match)

            # 3. Limpiar memoria (Fantamas)
            for pid in list(self.posiciones_activas.keys()):
                if pid not in real_ids:
                    del self.posiciones_activas[pid]

        except Exception as e:
            self.log.log_error(f"Error Sync: {e}")

    def _crear_sl_emergencia(self, pos):
        """Crea SL al 10% si no existe."""
        entry = pos['entry_price']
        side = pos['side']
        qty = pos['qty']
        sl_price = entry * 0.9 if side == 'LONG' else entry * 1.1
        self.om.update_stop_loss(pos['symbol'], side, sl_price, qty)