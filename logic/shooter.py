# =============================================================================
# UBICACIÓN: logic/shooter.py
# DESCRIPCIÓN: SHOOTER V19.6 (SMART RISK + SHADOW PRESERVATION)
# =============================================================================

from config.config import Config

class Shooter:
    """
    SHOOTER TRÍADA V19.6:
    - Lógica GAMMA: Control por "Unidades de Riesgo" (Smart Risk).
      * Re-entrada permitida si DD > 1.2% o Posición Blindada.
      * Máximo 2 cargas por sentido.
      * 3er cupo reservado para Cobertura.
    - Lógica SHADOW: Preservada (Grid Spacing).
    - Lógica SWING: Preservada.
    """
    def __init__(self, order_manager, financials):
        self.cfg = Config
        self.om = order_manager
        self.fin = financials 
        # Memoria temporal para evitar duplicados en el mismo milisegundo
        self.memory = {}
        
        try:
            from logs.system_logger import SystemLogger
            self.log = SystemLogger()
        except: self.log = None

    def _log(self, msg):
        if self.log: self.log.registrar_actividad("SHOOTER", msg)
        else: print(f"[SHOOTER] {msg}")

    def validar_y_crear_plan(self, signal, open_positions_dict):
        """
        Valida la señal contra la lógica de Cupos Dinámicos y Estrategia.
        """
        strategy = signal.get('strategy')
        side = signal.get('signal') # LONG/SHORT
        price = float(signal.get('price'))
        timestamp = signal.get('timestamp')
        
        # 1. Candado Temporal (Evita disparar 2 veces la misma señal exacta)
        memory_key = f"{strategy}_{side}_{timestamp}"
        if memory_key in self.memory: return None

        # 2. VALIDACIÓN INTELIGENTE (Reemplaza a los validadores antiguos para GAMMA)
        # Gestiona cupos globales, re-entradas y martingalas tácticas.
        if not self._validar_reglas_inteligentes(signal, open_positions_dict):
            return None

        # 3. VALIDACIÓN ESPECÍFICA SHADOW (PRESERVADA)
        # Si la estrategia es Shadow, verificamos su espaciado de grilla.
        if strategy == 'SHADOW':
            if not self._validar_grid_spacing(signal, open_positions_dict):
                return None

        # === APROBADO ===
        self.memory[memory_key] = True 
        if len(self.memory) > 100: self.memory.clear()

        # Construcción del Plan
        plan = {
            'symbol': self.cfg.SYMBOL,
            'strategy': strategy,
            'side': side,
            'mode': signal.get('mode'),
            'entry_price': price,
            'timestamp': timestamp
        }

        # Configuración según estrategia
        if strategy == 'GAMMA':
            return self._configurar_gamma_v4_6(plan)
        elif strategy == 'SWING':
            return self._configurar_swing(plan)
        elif strategy == 'SHADOW':
            return self._configurar_shadow(plan, signal.get('atr', 0))
            
        return None

    def _validar_reglas_inteligentes(self, signal, open_positions):
        """
        NÚCLEO LÓGICO V19.5: Decide si se dispara o no basado en "Cargas".
        """
        side = signal['signal']
        strategy = signal.get('strategy')
        symbol = self.cfg.SYMBOL
        
        # Si no es GAMMA, usamos una validación de cupos simplificada (Legacy)
        if strategy != 'GAMMA':
            return self._validar_cupos_legacy(strategy, open_positions)

        # --- LÓGICA AVANZADA GAMMA ---
        key = f"{symbol}_{side}"
        existing_pos = open_positions.get(key)
        
        # A. Control de Cupos Globales (Máx 3 Slots)
        total_slots_used = len(open_positions)
        if total_slots_used >= self.cfg.MAX_RISK_SLOTS:
            # Si está lleno, solo permitimos si es una Cobertura REAL (cambio de sentido)
            # Pero para seguridad máxima, si está lleno, rechazamos.
            self._log(f"⛔ Rechazado: Cupos Globales Llenos ({total_slots_used}/3).")
            return False

        # B. Si NO existe posición en ese sentido (Nueva Entrada)
        if not existing_pos:
            # Verificamos si es el 3er cupo (Reservado para Cobertura)
            if total_slots_used == 2:
                # Si tengo 2 operaciones, la 3ra debe ser del lado contrario.
                lados_ocupados = [p['side'] for p in open_positions.values()]
                if side in lados_ocupados:
                    self._log(f"⛔ Rechazado: 3er Cupo reservado para Cobertura (Lado opuesto).")
                    return False
                else:
                    self._log(f"🛡️ Aprobado: Activando Cobertura (Cupo 3).")
                    return True
            return True # 0 o 1 operación previa -> Entrada Libre

        # C. Si YA EXISTE posición (Evaluamos Re-entrada)
        
        # 1. Calcular Tamaño de 1 Unidad Estándar (Risk Unit)
        balance = self.fin.get_balance_total()
        cfg = self.cfg.GammaConfig
        std_unit_usd = (balance * cfg.PCT_CAPITAL_PER_TRADE) * self.cfg.LEVERAGE
        
        # 2. Medir la posición actual
        current_qty = float(existing_pos['qty'])
        current_entry = float(existing_pos['entry_price'])
        current_notional = current_qty * current_entry
        
        # Ratio de Cargas
        risk_units = current_notional / std_unit_usd if std_unit_usd > 0 else 99
        
        # LÍMITE: Si ya tiene > 1.6 cargas, es una posición doble. NO MÁS.
        if risk_units > 1.6:
            self._log(f"⛔ Rechazado: Posición {side} ya tiene 2 Cargas ({risk_units:.1f}u).")
            return False
            
        # --- TIENE 1 SOLA CARGA: EVALUAR CONDICIONES ---
        
        # Regla 1: Precio en Contra > 1.2% (Rescate)
        current_price = signal['price']
        if side == 'LONG':
            pnl_pct = (current_price - current_entry) / current_entry
        else:
            pnl_pct = (current_entry - current_price) / current_entry
            
        if pnl_pct <= -0.012: # -1.2%
            self._log(f"✅ Re-entrada Aprobada: Precio en contra {pnl_pct*100:.2f}% (> 1.2%).")
            return True
            
        # Regla 2: Posición Blindada (Oportunidad / Pyramiding)
        if existing_pos.get('be_triggered', False) or existing_pos.get('tp1_hit', False):
            self._log(f"✅ Re-entrada Aprobada: Posición original blindada (BE/TP1).")
            return True
            
        self._log(f"⛔ Rechazado: Re-entrada prematura. PnL: {pnl_pct*100:.2f}%")
        return False

    # --- VALIDACIONES LEGACY (PRESERVADAS PARA SHADOW/SWING) ---

    def _validar_cupos_legacy(self, strategy, open_positions):
        """Validador simple para estrategias no-Gamma."""
        count = 0
        for pos in open_positions.values():
            if pos.get('strategy') == strategy: count += 1
                
        if strategy == 'SWING' and count >= self.cfg.MAX_SWING_SLOTS: return False
        if strategy == 'SHADOW' and count >= self.cfg.MAX_SHADOW_SLOTS: return False
        if len(open_positions) >= self.cfg.MAX_RISK_SLOTS: return False
        return True

    def _validar_grid_spacing(self, signal, open_positions):
        """
        Lógica SHADOW (Preservada): Evita entradas pegadas en la grilla.
        """
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

    # --- CONFIGURADORES (INTACTOS) ---

    def _configurar_gamma_v4_6(self, plan):
        cfg = self.cfg.GammaConfig
        plan['execution_type'] = 'MARKET'
        
        balance = self.fin.get_balance_total()
        if balance <= 0: balance = 1000 
        invested_usd = balance * cfg.PCT_CAPITAL_PER_TRADE * self.cfg.LEVERAGE
        
        if plan['entry_price'] > 0:
            plan['qty'] = invested_usd / plan['entry_price']
        else: plan['qty'] = 0
        
        mode = plan.get('mode', 'GAMMA_NORMAL')
        sl_pct = cfg.SL_NORMAL if 'NORMAL' in mode else cfg.SL_HEDGE
        entry = plan['entry_price']
        
        if plan['side'] == 'LONG':
            plan['sl_price'] = entry * (1 - sl_pct)
            tp1 = entry * (1 + cfg.TP_1_DIST)
            tp2 = entry * (1 + cfg.TP_2_DIST)
        else:
            plan['sl_price'] = entry * (1 + sl_pct)
            tp1 = entry * (1 - cfg.TP_1_DIST)
            tp2 = entry * (1 - cfg.TP_2_DIST)
            
        plan['tp_map'] = [
            {'id': 'TP1', 'price_target': tp1, 'qty_pct': cfg.TP_1_QTY},
            {'id': 'TP2', 'price_target': tp2, 'qty_pct': cfg.TP_2_QTY}
        ]
        return plan

    def _configurar_swing(self, plan):
        cfg = self.cfg.SwingConfig
        plan['execution_type'] = 'LIMIT'
        plan['qty'] = self._calcular_qty(cfg.RISK_USD_PER_TRADE, plan['entry_price'])
        entry = plan['entry_price']
        if plan['side'] == 'LONG': plan['sl_price'] = entry * (1 - cfg.SL_INIT_NORMAL)
        else: plan['sl_price'] = entry * (1 + cfg.SL_INIT_NORMAL)
        return plan

    def _configurar_shadow(self, plan, atr):
        cfg = self.cfg.ShadowConfig
        plan['execution_type'] = 'LIMIT'
        plan['qty'] = self._calcular_qty(cfg.BASE_UNIT_USD, plan['entry_price'])
        sl_dist = atr * 10 if atr > 0 else plan['entry_price'] * 0.10
        entry = plan['entry_price']
        if plan['side'] == 'LONG': plan['sl_price'] = entry - sl_dist
        else: plan['sl_price'] = entry + sl_dist
        return plan

    def _calcular_qty(self, usd_amount, price):
        return 0 if price == 0 else usd_amount / price