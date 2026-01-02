# =============================================================================
# UBICACIÓN: logic/shooter.py
# DESCRIPCIÓN: SHOOTER TRÍADA V17.8 (VALIDADOR DE ESTRATEGIA Y CUPOS)
# =============================================================================

from config.config import Config

class Shooter:
    """
    SHOOTER TRÍADA:
    - Transforma Señales del Brain en Planes de Ejecución.
    - Define execution_type (MARKET para Gamma, LIMIT para Swing/Shadow).
    - Gestiona Cupos por Estrategia.
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
        signal: dict generado por Brain.
        open_positions_dict: dict de Comptroller con posiciones activas.
        """
        strategy = signal.get('strategy')
        side = signal.get('signal') # LONG/SHORT
        price = signal.get('price')
        
        # 1. Validación de Cupos (Risk Management)
        if not self._validar_cupos(strategy, open_positions_dict):
            self._log(f"⛔ Cupos llenos para {strategy}.")
            return None

        # 2. Validación de Espaciado (Shadow Grid)
        if strategy == 'SHADOW':
            if not self._validar_grid_spacing(signal, open_positions_dict):
                return None

        # 3. Construcción del Plan
        plan = {
            'symbol': self.cfg.SYMBOL,
            'strategy': strategy,
            'side': side,
            'mode': signal.get('mode'),
            'entry_price': price,
            'timestamp': signal.get('timestamp')
        }

        # 4. Configuración Específica (Tamaño, Tipo, SL/TP)
        if strategy == 'GAMMA':
            return self._configurar_gamma(plan)
        elif strategy == 'SWING':
            return self._configurar_swing(plan)
        elif strategy == 'SHADOW':
            return self._configurar_shadow(plan, signal.get('atr', 0))
            
        return None

    # --- CONFIGURADORES POR ESTRATEGIA ---

    def _configurar_gamma(self, plan):
        cfg = self.cfg.GammaConfig
        
        # Gamma usa MARKET para entrada rápida (Scalping)
        plan['execution_type'] = 'MARKET'
        
        # Cantidad
        qty = self._calcular_qty(cfg.RISK_USD_PER_TRADE, plan['entry_price'])
        plan['qty'] = qty
        
        # SL Inicial
        mode = plan.get('mode', 'GAMMA_NORMAL')
        sl_pct = cfg.SL_NORMAL if 'NORMAL' in mode else cfg.SL_HEDGE
        
        entry = plan['entry_price']
        if plan['side'] == 'LONG':
            plan['sl_price'] = entry * (1 - sl_pct)
        else:
            plan['sl_price'] = entry * (1 + sl_pct)
            
        return plan

    def _configurar_swing(self, plan):
        cfg = self.cfg.SwingConfig
        
        # Swing usa LIMIT para mejor precio (opcional, aqui usaremos LIMIT al precio actual)
        plan['execution_type'] = 'LIMIT'
        
        qty = self._calcular_qty(cfg.RISK_USD_PER_TRADE, plan['entry_price'])
        plan['qty'] = qty
        
        # SL Swing Estructural (amplio)
        entry = plan['entry_price']
        if plan['side'] == 'LONG':
            plan['sl_price'] = entry * (1 - cfg.SL_INIT_NORMAL)
        else:
            plan['sl_price'] = entry * (1 + cfg.SL_INIT_NORMAL)
            
        return plan

    def _configurar_shadow(self, plan, atr):
        cfg = self.cfg.ShadowConfig
        
        # Shadow usa LIMIT en las bandas
        plan['execution_type'] = 'LIMIT'
        
        qty = self._calcular_qty(cfg.BASE_UNIT_USD, plan['entry_price'])
        plan['qty'] = qty
        
        # Shadow gestiona SL dinámico o "catástrofe"
        # Ponemos un SL lejano de seguridad, la gestión real es por ATR/Bandas en Comptroller
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
        raw = usd_amount / price
        # Redondeo ciego simple, OrderManager aplica la precisión final
        return raw

    def _validar_cupos(self, strategy, open_positions):
        """Verifica si hay espacio según Config."""
        count = 0
        for pos in open_positions.values():
            if pos.get('strategy') == strategy:
                count += 1
                
        if strategy == 'GAMMA' and count >= self.cfg.MAX_GAMMA_SLOTS: return False
        if strategy == 'SWING' and count >= self.cfg.MAX_SWING_SLOTS: return False
        if strategy == 'SHADOW' and count >= self.cfg.MAX_SHADOW_SLOTS: return False
        
        return True

    def _validar_grid_spacing(self, signal, open_positions):
        """Shadow: Evita entradas pegadas."""
        cfg = self.cfg.ShadowConfig
        atr = signal.get('atr', 0)
        price = signal.get('price')
        side = signal.get('signal')
        
        if atr == 0: return True # Sin ATR no filtramos (fallback)
        
        last_price = 0
        found = False
        
        # Buscar la última entrada de Shadow en la misma dirección
        # Ordenamos por fecha de entrada idealmente, aqui simplificado
        for pos in open_positions.values():
            if pos.get('strategy') == 'SHADOW' and pos.get('side') == side:
                entry = float(pos.get('entry_price', 0))
                last_price = entry # Tomamos una cualquiera existente (ideal: la más cercana)
                found = True
        
        if found:
            dist = abs(price - last_price)
            min_dist = atr * cfg.MIN_SPACING_ATR
            if dist < min_dist:
                return False # Muy cerca
        
        return True