# =============================================================================
# UBICACIÓN: logic/shooter.py
# DESCRIPCIÓN: Shooter Híbrido V15 (Smart Slots + Triad Logic)
# =============================================================================

from config.config import Config

class Shooter:
    """
    SHOOTER TRÍADA (V15.0):
    - Gestión: Gamma (Smart), Swing (Fractional), Shadow (Cascading).
    - Smart Slots: Ignora operaciones en Break Even.
    - Validación de duplicados y capital mínimo.
    """
    def __init__(self, order_manager, financials):
        # Nota: Recibimos order_manager para consistencia, aunque este módulo
        # devuelve planes, el main o el mismo shooter podrían ejecutar.
        # Mantenemos la firma __init__ compatible.
        self.cfg = Config
        self.om = order_manager
        self.fin = financials 
        # Logger se instancia internamente o se pasa, asumiremos inyección o uso de print/logger global
        # Para compatibilidad con tu código previo, usaremos print o self.log si existiera
        from logs.system_logger import SystemLogger
        self.log = SystemLogger()

    def validar_y_crear_plan(self, signal, open_positions_dict):
        """
        Valida cupos, riesgo y crea el plan de orden.
        """
        # -----------------------------------------------------------
        # 1. CONTEO INTELIGENTE DE CUPOS (Smart Slots)
        # -----------------------------------------------------------
        total_risk_active = 0
        gamma_risk_active = 0
        swing_risk_active = 0
        shadow_risk_active = 0
        
        for pos in open_positions_dict.values():
            # Verificar si la posición sigue en riesgo
            entry = float(pos.get('entry_price', 0))
            sl = float(pos.get('sl_price', 0))
            side = pos.get('side', '')
            strat = pos.get('strategy', 'UNKNOWN')
            
            en_riesgo = True
            
            # Lógica de "Risk Free" (Solo aplica si tiene SL válido)
            if entry > 0 and sl > 0:
                if side == 'LONG' and sl >= entry: en_riesgo = False
                if side == 'SHORT' and sl <= entry: en_riesgo = False
            
            # Shadow Hunter siempre cuenta como riesgo hasta que cierra (Cascada)
            if 'SHADOW' in strat: en_riesgo = True 

            if en_riesgo:
                total_risk_active += 1
                if 'GAMMA' in strat: gamma_risk_active += 1
                if 'SWING' in strat: swing_risk_active += 1
                if 'SHADOW' in strat: shadow_risk_active += 1

        # Validación de Límites (Config)
        # Asumimos que Config tiene estos límites (agregados en paso anterior)
        MAX_RISK_TOTAL = getattr(self.cfg, 'MAX_RISK_TOTAL', 5)
        
        if total_risk_active >= MAX_RISK_TOTAL:
            return None

        strat_name = signal.get('strategy', 'UNKNOWN')
        
        # Filtros por Estrategia
        if 'GAMMA' in strat_name and gamma_risk_active >= getattr(self.cfg, 'MAX_RISK_GAMMA', 2): return None
        if 'SWING' in strat_name and swing_risk_active >= getattr(self.cfg, 'MAX_RISK_SWING', 2): return None
        if 'SHADOW' in strat_name and shadow_risk_active >= getattr(self.cfg, 'SH_MAX_SLOTS', 5): return None

        # -----------------------------------------------------------
        # 2. FILTROS Y PLANIFICACIÓN
        # -----------------------------------------------------------
        if not self._validar_overlap(signal, open_positions_dict): return None

        balance = self.fin.get_balance_total()
        
        # Filtro de pobreza extrema
        if balance < 10.0: 
            self.log.log_warn(f"Shooter: Balance insuficiente ({balance})")
            return None
            
        # Enrutamiento de estrategia
        if 'SHADOW' in strat_name:
            return self._plan_shadow_v2(signal, balance)
        elif 'GAMMA' in strat_name:
            return self._plan_gamma_v7(signal, balance)
        elif 'SWING' in strat_name:
            return self._plan_swing_v3(signal, balance)
        
        return None

    # --- PLANIFICADORES ---

    def _calcular_qty(self, risk_usd, price):
        raw = risk_usd / price
        return round(raw, self.cfg.QTY_PRECISION)

    def _plan_shadow_v2(self, signal, balance):
        entry = signal['price']
        # Shadow usa tamaño fijo (Base Unit)
        base_usd = self.cfg.SH_BASE_UNIT_USD
        qty = self._calcular_qty(base_usd, entry)
        
        if (qty * entry) < 5.1: return None
        
        return {
            'strategy': 'SHADOW_V2',
            'mode': signal.get('mode', 'CASCADING'),
            'symbol': self.cfg.SYMBOL,
            'side': signal['side'],
            'qty': qty,
            'entry_price': entry,
            'sl_price': 0.0, # Shadow usa trailing dinámico, no SL fijo inicial (o uno de emergencia lejos)
            'tp_hard_price': 0.0,
            'management_type': 'SHADOW_CASCADING'
        }

    def _plan_gamma_v7(self, signal, balance):
        entry = signal['price']
        side = signal['side']
        mode = signal.get('mode', 'GAMMA_NORMAL')
        
        # Configuración
        if 'HEDGE' in mode:
            sl_pct = self.cfg.G_SL_HEDGE
            tp_pct = self.cfg.G_TP_HEDGE
        else:
            sl_pct = self.cfg.G_SL_NORMAL
            tp_pct = self.cfg.G_TP_NORMAL
            
        # Precios
        if side == 'LONG':
            sl_price = entry * (1 - sl_pct)
            tp_hard = entry * (1 + tp_pct)
        else:
            sl_price = entry * (1 + sl_pct)
            tp_hard = entry * (1 - tp_pct)
            
        # Capital: Riesgo fijo o %
        risk_per_trade = self.cfg.INITIAL_CAPITAL * 0.10 # Ejemplo 10% del capital base asignado
        qty = self._calcular_qty(risk_per_trade, entry)
        
        if (qty * entry) < 5.1: return None 
        
        return {
            'strategy': 'GAMMA',
            'mode': mode,
            'symbol': self.cfg.SYMBOL,
            'side': side,
            'qty': qty,
            'entry_price': entry,
            'sl_price': sl_price,
            'tp_hard_price': tp_hard,
            'management_type': 'DYNAMIC_TRAILING'
        }

    def _plan_swing_v3(self, signal, balance):
        entry = signal['price']
        side = signal['side']
        
        sl_pct = self.cfg.S_SL_INIT_NORM
        
        if side == 'LONG': sl_price = entry * (1 - sl_pct)
        else: sl_price = entry * (1 + sl_pct)
        
        # Swing usa más capital
        risk_swing = self.cfg.INITIAL_CAPITAL * 0.15 
        qty = self._calcular_qty(risk_swing, entry)
        
        if (qty * entry) < 5.1: return None

        return {
            'strategy': 'SWING',
            'mode': signal.get('mode', 'SWING_NORMAL'),
            'symbol': self.cfg.SYMBOL,
            'side': side,
            'qty': qty,
            'entry_price': entry,
            'sl_price': sl_price,
            'management_type': 'FRACTIONAL_SWING',
            # Metadatos para gestión fraccionada
            'tp1_dist': self.cfg.S_TP1_DIST,
            'tp2_dist': self.cfg.S_TP2_DIST,
            'tp1_qty': self.cfg.S_TP1_QTY,
            'tp2_qty': self.cfg.S_TP2_QTY
        }

    def _validar_overlap(self, signal, open_positions):
        """Evita duplicar entradas en el mismo precio."""
        if not open_positions: return True
        current_price = signal['price']
        side = signal['side']
        # Shadow Hunter permite overlap si el espaciado ATR lo valida (eso lo hace Brain)
        # Pero aquí prevenimos errores de doble disparo inmediato
        umbral = 0.002 # 0.2%
        
        for pos in open_positions.values():
            if pos['side'] == side and pos['strategy'] == signal['strategy']:
                entry = float(pos.get('entry_price', 0.0))
                if entry > 0 and (abs(current_price - entry)/entry) < umbral:
                    return False
        return True