# =============================================================================
# UBICACIÓN: execution/comptroller.py
# DESCRIPCIÓN: CONTRALOR V18 (GAMMA DYNAMIC + LEGACY SUPPORT)
# =============================================================================

from config.config import Config
try:
    from logs.system_logger import SystemLogger
except ImportError:
    SystemLogger = None

class Comptroller:
    def __init__(self, config, order_manager, financials, logger):
        self.cfg = config
        self.om = order_manager
        self.fin = financials
        self.log = logger
        self.posiciones_activas = {} 

    def aceptar_custodia(self, paquete_orden):
        symbol = paquete_orden['symbol']
        key = f"{symbol}_{paquete_orden['side']}"
        
        # Inicializar métricas
        paquete_orden['max_price'] = paquete_orden['entry_price'] 
        paquete_orden['min_price'] = paquete_orden['entry_price']
        paquete_orden['be_triggered'] = False
        paquete_orden['tp1_hit'] = False 
        
        self.posiciones_activas[key] = paquete_orden
        if self.log: self.log.registrar_actividad("COMP", f"🛡️ Custodia iniciada: {key}")

    def auditar_posiciones(self, current_price):
        if not self.posiciones_activas: return

        for key, pos in list(self.posiciones_activas.items()):
            pos['current_price'] = current_price
            side = pos['side']
            entry = float(pos['entry_price'])
            
            # Actualizar High/Low locales
            if current_price > pos['max_price']: pos['max_price'] = current_price
            if current_price < pos['min_price']: pos['min_price'] = current_price

            # PnL %
            if side == 'LONG': pnl_pct = (current_price - entry) / entry
            else: pnl_pct = (entry - current_price) / entry
            
            pos['pnl_pct'] = pnl_pct

            # Verificar SL en Financials
            tiene_sl, sl_real, _ = self.fin.verificar_si_tiene_sl_local(side)
            if tiene_sl: pos['sl_price'] = sl_real

            # ROUTING DE ESTRATEGIA
            strategy = pos.get('strategy', 'MANUAL')
            
            if strategy == 'GAMMA':
                self._gestion_gamma_v4_6(pos, current_price, pnl_pct)
            elif strategy == 'SWING':
                self._gestion_swing(pos, current_price, pnl_pct)
            elif strategy == 'SHADOW':
                self._gestion_shadow(pos, current_price, pnl_pct)

    def _gestion_gamma_v4_6(self, pos, curr, pnl_pct):
        """Gamma V4.6: BE al 1.5% + Trailing."""
        cfg = self.cfg.GammaConfig
        
        # 1. BREAK EVEN AVANZADO
        if not pos['be_triggered']:
            if pnl_pct >= cfg.BE_ACTIVATION:
                if pos['side'] == 'LONG':
                    nuevo_sl = pos['entry_price'] * (1 + cfg.BE_PROFIT)
                else:
                    nuevo_sl = pos['entry_price'] * (1 - cfg.BE_PROFIT)
                
                self._mover_sl(pos, nuevo_sl)
                pos['be_triggered'] = True
                if self.log: self.log.registrar_actividad("COMP", "🔓 Break Even Activado (+0.5% Asegurado)")

        # 2. TRAILING STOP
        if pos['be_triggered']:
            distancia = cfg.TRAILING_DIST
            if pos['side'] == 'LONG':
                propuesto = curr * (1 - distancia)
                if propuesto > pos['sl_price']: 
                    self._mover_sl(pos, propuesto)
            else:
                propuesto = curr * (1 + distancia)
                if propuesto < pos['sl_price']: 
                    self._mover_sl(pos, propuesto)

    def _gestion_swing(self, pos, curr, pnl_pct):
        """Gestión Swing Original (TP1 + BE)."""
        cfg = self.cfg.SwingConfig
        
        if not pos['tp1_hit'] and pnl_pct >= cfg.TP1_DIST:
            qty_total = float(pos['qty'])
            qty_close = qty_total * cfg.TP1_QTY_PCT
            
            if self.log: self.log.registrar_actividad("COMP", f"⭐ TP1 SWING alcanzado. Cerrando {qty_close:.3f}")
            
            if self.om.reducir_posicion(pos['symbol'], qty_close, "TP1_SWING"):
                pos['qty'] -= qty_close
                pos['tp1_hit'] = True
                self._mover_sl(pos, pos['entry_price'])

    def _gestion_shadow(self, pos, curr, pnl_pct):
        """Gestión Shadow (Placeholder/Basic)."""
        pass

    def _mover_sl(self, pos, nuevo_precio):
        if abs(nuevo_precio - pos['sl_price']) / pos['sl_price'] < 0.001: return
        exito = self.om.actualizar_stop_loss(pos['symbol'], pos['side'], nuevo_precio)
        if exito: pos['sl_price'] = nuevo_precio

    def sincronizar_con_exchange(self):
        try:
            real_positions = self.fin.obtener_posiciones_activas_simple()
            real_keys = set(f"{p['symbol']}_{p['side']}" for p in real_positions)
            
            keys_to_delete = [k for k in self.posiciones_activas if k not in real_keys]
            
            for k in keys_to_delete:
                del self.posiciones_activas[k]
                if self.log: self.log.registrar_actividad("COMP", f"🏳️ Posición Finalizada: {k}")
        except Exception: pass