# =============================================================================
# UBICACIÓN: logic/shooter.py
# DESCRIPCIÓN: SHOOTER V18 (GAMMA V4.6 + LEGACY SUPPORT)
# =============================================================================

from config.config import Config

class Shooter:
    """
    SHOOTER TRÍADA:
    - Transforma Señales del Brain en Planes de Ejecución.
    - Implementa lógica Gamma V4.6.
    - Preserva lógica Swing y Shadow.
    """
    def __init__(self, order_manager, financials):
        self.cfg = Config
        self.om = order_manager
        self.fin = financials 
        try:
            from logs.system_logger import SystemLogger
            self.log = SystemLogger()
        except: self.log = None

    def _log(self, msg):
        if self.log: self.log.registrar_actividad("SHOOTER", msg)
        else: print(f"[SHOOTER] {msg}")

    def validar_y_crear_plan(self, signal, open_positions_dict):
        """
        Valida cupos y crea el plan de orden.
        """
        strategy = signal.get('strategy')
        side = signal.get('signal') # LONG/SHORT
        price = signal.get('price')
        
        # 1. Validación de Cupos (Risk Management)
        if not self._validar_cupos(strategy, open_positions_dict):
            return None

        # 2. Validación de Espaciado (Shadow Grid)
        if strategy == 'SHADOW':
            if not self._validar_grid_spacing(signal, open_positions_dict):
                return None

        # 3. Construcción del Plan Base
        plan = {
            'symbol': self.cfg.SYMBOL,
            'strategy': strategy,
            'side': side,
            'mode': signal.get('mode'),
            'entry_price': price,
            'timestamp': signal.get('timestamp')
        }

        # 4. Configuración Específica
        if strategy == 'GAMMA':
            return self._configurar_gamma_v4_6(plan)
        elif strategy == 'SWING':
            return self._configurar_swing(plan)
        elif strategy == 'SHADOW':
            return self._configurar_shadow(plan, signal.get('atr', 0))
            
        return None

    # --- CONFIGURADORES POR ESTRATEGIA ---

    def _configurar_gamma_v4_6(self, plan):
        """Configuración Gamma V4.6 (Actualizada)"""
        cfg = self.cfg.GammaConfig
        
        # A. Ejecución: MARKET (Scalping)
        plan['execution_type'] = 'MARKET'
        
        # B. Lotaje
        balance = self.fin.get_balance_total()
        if balance <= 0: balance = 1000 
        
        # Inversión = Balance * % por Trade * Apalancamiento Global
        invested_usd = balance * cfg.PCT_CAPITAL_PER_TRADE * self.cfg.LEVERAGE
        plan['qty'] = invested_usd / plan['entry_price']
        
        # C. Stop Loss (Normal vs Hedge)
        mode = plan.get('mode', 'GAMMA_NORMAL')
        sl_pct = cfg.SL_NORMAL if 'NORMAL' in mode else cfg.SL_HEDGE
        
        entry = plan['entry_price']
        if plan['side'] == 'LONG':
            plan['sl_price'] = entry * (1 - sl_pct)
        else:
            plan['sl_price'] = entry * (1 + sl_pct)
            
        # D. Take Profits Escalonados
        tps = []
        
        # TP1 (Vende 40%)
        tp1_price = entry * (1 + cfg.TP_1_DIST) if plan['side'] == 'LONG' else entry * (1 - cfg.TP_1_DIST)
        tps.append({'id': 'TP1', 'price_target': tp1_price, 'qty_pct': cfg.TP_1_QTY})
        
        # TP2 (Vende 30%)
        tp2_price = entry * (1 + cfg.TP_2_DIST) if plan['side'] == 'LONG' else entry * (1 - cfg.TP_2_DIST)
        tps.append({'id': 'TP2', 'price_target': tp2_price, 'qty_pct': cfg.TP_2_QTY})
        
        plan['tp_map'] = tps
        return plan

    def _configurar_swing(self, plan):
        """Configuración Swing (Preservada)."""
        cfg = self.cfg.SwingConfig
        plan['execution_type'] = 'LIMIT'
        
        plan['qty'] = self._calcular_qty(cfg.RISK_USD_PER_TRADE, plan['entry_price'])
        
        entry = plan['entry_price']
        if plan['side'] == 'LONG':
            plan['sl_price'] = entry * (1 - cfg.SL_INIT_NORMAL)
        else:
            plan['sl_price'] = entry * (1 + cfg.SL_INIT_NORMAL)
            
        return plan

    def _configurar_shadow(self, plan, atr):
        """Configuración Shadow (Preservada)."""
        cfg = self.cfg.ShadowConfig
        plan['execution_type'] = 'LIMIT'
        
        plan['qty'] = self._calcular_qty(cfg.BASE_UNIT_USD, plan['entry_price'])
        
        # Shadow Catastrophe SL
        sl_dist = atr * 10 if atr > 0 else plan['entry_price'] * 0.10
        entry = plan['entry_price']
        
        if plan['side'] == 'LONG':
            plan['sl_price'] = entry - sl_dist
        else:
            plan['sl_price'] = entry + sl_dist
            
        return plan

    # --- UTILIDADES ---

    def _calcular_qty(self, usd_amount, price):
        if price == 0: return 0
        return usd_amount / price

    def _validar_cupos(self, strategy, open_positions):
        count = 0
        for pos in open_positions.values():
            if pos.get('strategy') == strategy:
                count += 1
                
        if strategy == 'GAMMA' and count >= self.cfg.MAX_GAMMA_SLOTS: return False
        if strategy == 'SWING' and count >= self.cfg.MAX_SWING_SLOTS: return False
        if strategy == 'SHADOW' and count >= self.cfg.MAX_SHADOW_SLOTS: return False
        
        # Cupo Global del Sistema
        if len(open_positions) >= self.cfg.MAX_RISK_SLOTS: return False
        
        return True

    def _validar_grid_spacing(self, signal, open_positions):
        """Shadow: Evita entradas pegadas."""
        cfg = self.cfg.ShadowConfig
        atr = signal.get('atr', 0)
        price = signal.get('price')
        side = signal.get('signal')
        
        if atr == 0: return True 
        
        found = False
        last_price = 0
        
        for pos in open_positions.values():
            if pos.get('strategy') == 'SHADOW' and pos.get('side') == side:
                entry = float(pos.get('entry_price', 0))
                last_price = entry
                found = True
        
        if found:
            dist = abs(price - last_price)
            min_dist = atr * cfg.MIN_SPACING_ATR
            if dist < min_dist:
                return False 
        
        return True