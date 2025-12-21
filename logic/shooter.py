from config.config import Config

class Shooter:
    """
    SHOOTER HÍBRIDO (V14.1 - SMART SLOTS):
    - Gestión de Cupos Dinámica (Ignora operaciones en Break Even).
    - Control de Precisión de Decimales.
    """
    def __init__(self, config, logger, financials):
        self.cfg = config
        self.log = logger
        self.fin = financials 

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
        
        for pos in open_positions_dict.values():
            # Verificar si la posición sigue en riesgo
            entry = float(pos.get('entry_price', 0))
            sl = float(pos.get('sl_price', 0))
            side = pos.get('side', '')
            
            en_riesgo = True
            
            # Lógica de "Risk Free":
            # Si es LONG y el SL >= Entry, ya no pierdo dinero.
            # Si es SHORT y el SL <= Entry, ya no pierdo dinero.
            if entry > 0 and sl > 0:
                if side == 'LONG' and sl >= entry: en_riesgo = False
                if side == 'SHORT' and sl <= entry: en_riesgo = False
            
            if en_riesgo:
                total_risk_active += 1
                strat = pos.get('strategy', '')
                if 'GAMMA' in strat: gamma_risk_active += 1
                if 'SWING' in strat: swing_risk_active += 1

        # Validación Global
        if total_risk_active >= self.cfg.MAX_RISK_SLOTS:
            self.log.registrar_actividad("SHOOTER", f"⛔ Cupos Globales llenos ({total_risk_active} en riesgo)")
            return None

        # Validación por Estrategia
        strat_name = signal.get('strategy', 'UNKNOWN')
        if 'GAMMA' in strat_name and gamma_risk_active >= self.cfg.MAX_GAMMA_SLOTS: return None
        if 'SWING' in strat_name and swing_risk_active >= self.cfg.MAX_SWING_SLOTS: return None

        # -----------------------------------------------------------
        # 2. FILTROS Y PLANIFICACIÓN
        # -----------------------------------------------------------
        if not self._validar_overlap(signal, open_positions_dict): return None

        balance = self.fin.get_balance_total()
        params = signal.get('params')
        if not params: return None
        
        # Filtro de pobreza extrema
        if balance < 10.0: return None
            
        risk_real = min(params.RISK_USD_FIXED, balance)
        
        # Enrutamiento de estrategia
        if 'GAMMA' in strat_name:
            return self._plan_gamma_v7(signal, risk_real, params)
        elif 'SWING' in strat_name:
            return self._plan_swing_v3(signal, risk_real, params)
        
        return None

    # --- MÉTODOS AUXILIARES ---

    def _calcular_qty(self, risk_usd, entry_price):
        """Calcula Qty respetando la precisión del activo."""
        raw_qty = risk_usd / entry_price
        precision = getattr(self.cfg, 'QTY_PRECISION', 1) 
        return round(raw_qty, precision)

    def _plan_gamma_v7(self, signal, risk_usd, params):
        entry = signal['price']
        side = signal['side']
        mode = signal.get('mode', 'NORMAL')
        
        # SL/TP Config
        if mode == 'HEDGE':
            sl_pct = params.SL_HEDGE
            tp_pct = params.TP_HEDGE
        else:
            sl_pct = params.SL_NORMAL
            tp_pct = params.TP_NORMAL
            
        if side == 'LONG':
            sl_price = entry * (1 - sl_pct)
            tp_hard = entry * (1 + params.GAMMA_HARD_TP_PCT)
        else:
            sl_price = entry * (1 + sl_pct)
            tp_hard = entry * (1 - params.GAMMA_HARD_TP_PCT)
            
        qty = self._calcular_qty(risk_usd, entry)
        if (qty * entry) < 5.1: return None 
        
        return {
            'strategy': 'GAMMA_V7',
            'mode': mode,
            'symbol': self.cfg.SYMBOL,
            'side': side,
            'qty': qty,
            'entry_price': entry,
            'sl_price': sl_price,
            'tp_hard_price': tp_hard,
            'management_type': 'DYNAMIC_TRAILING' if params.GAMMA_TRAILING_ENABLED else 'STATIC',
            'params': params
        }

    def _plan_swing_v3(self, signal, risk_usd, params):
        entry = signal['price']
        side = signal['side']
        mode = signal.get('mode', 'NORMAL')
        stop_ref = signal.get('stop_ref')
        
        sl_dist_pct = params.SL_INIT_NORMAL
        
        # Ajuste dinámico de SL por estructura
        if stop_ref and stop_ref > 0:
            dist_ref = abs(entry - stop_ref) / entry
            if 0.005 < dist_ref < 0.10: 
                sl_dist_pct = dist_ref + 0.002
        
        if side == 'LONG': sl_price = entry * (1 - sl_dist_pct)
        else: sl_price = entry * (1 + sl_dist_pct)
        
        qty = self._calcular_qty(risk_usd, entry)
        if (qty * entry) < 5.1: return None

        return {
            'strategy': 'SWING_V3',
            'mode': mode,
            'symbol': self.cfg.SYMBOL,
            'side': side,
            'qty': qty,
            'entry_price': entry,
            'sl_price': sl_price,
            'tp_hard_price': 0.0,
            'management_type': 'FRACTIONAL_SWING',
            'params': params
        }

    def _validar_overlap(self, signal, open_positions):
        """Evita duplicar entradas en el mismo precio."""
        if not open_positions: return True
        current_price = signal['price']
        side = signal['side']
        umbral = 0.005 # 0.5% distancia mínima
        
        for pos in open_positions.values():
            if pos['side'] == side:
                entry = float(pos.get('entry_price', 0.0))
                if entry > 0 and (abs(current_price - entry)/entry) < umbral:
                    return False
        return True