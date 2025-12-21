from config.config import Config

class Shooter:
    """
    DEPARTAMENTO DE RIESGO Y PLANIFICACIÓN (Gestión de Riesgo V12.0):
    - Filtra señales duplicadas (mismo lado y precio cercano).
    - Ajusta el lotaje al capital real disponible (Downsizing).
    - Planifica Gamma con Trailing Dinámico y Sniper con salidas escalonadas.
    """
    def __init__(self, config, logger, financials):
        self.cfg = config
        self.log = logger
        self.fin = financials # Inyección de dependencia financiera
        self.sniper_cfg = self.cfg.SniperConfig
        self.gamma_cfg = self.cfg.GammaConfig

    def validar_y_crear_plan(self, signal, open_positions_dict):
        """
        Orquestador principal de validación y creación de planes.
        """
        # 1. FILTRO DE SATURACIÓN (Máx 2 posiciones simultáneas)
        if len(open_positions_dict) >= 2:
            return None

        # 2. FILTRO DE DUPLICADOS (Anti-Overlap)
        # Si ya tengo un LONG y el precio actual está a < 0.5% del precio de entrada, rechazo.
        if not self._validar_overlap(signal, open_positions_dict):
            return None

        # 3. SELECCIÓN DE ESTRATEGIA
        strategy = signal.get('strategy', 'UNKNOWN')
        if strategy == 'SCALPING_GAMMA':
            return self._plan_gamma(signal)
        else:
            return self._plan_sniper(signal)

    def _validar_overlap(self, signal, positions):
        """
        Evita abrir múltiples operaciones en el mismo punto de precio (Over-trading).
        """
        if not positions: return True
        
        current_price = signal['price']
        side = signal['side']
        umbral_overlap = 0.005 # 0.5%
        
        for pos in positions.values():
            if pos['side'] == side:
                entry_existente = float(pos.get('entry_price', 0.0))
                if entry_existente > 0:
                    diff_pct = abs(current_price - entry_existente) / entry_existente
                    if diff_pct < umbral_overlap:
                        self.log.registrar_actividad("SHOOTER", f"⛔ Señal rechazada: Duplicado de posición existente ({diff_pct:.2%})")
                        return False
        return True

    def _plan_gamma(self, signal):
        """
        Planificación para Gamma Scalping (Estrategia Refinada Trailing 1.5%)
        """
        entry_price = signal['price']
        side = signal['side']
        
        # A. DEFINICIÓN DE RIESGO
        risk_target = self.gamma_cfg.RISK_USD_FIXED
        
        # B. VERIFICACIÓN FINANCIERA
        balance_disponible = self.fin.get_balance_total()
        
        # Ajustamos el riesgo: Usamos lo que haya, hasta el máximo configurado
        risk_usd = min(risk_target, balance_disponible)
        
        # Filtro de pobreza: Si hay menos de $10, no operamos
        if risk_usd < 10.0:
            self.log.registrar_error("SHOOTER", f"Capital insuficiente (${risk_usd:.2f}) para operar Gamma.")
            return None

        # C. CÁLCULOS TÉCNICOS REFINADOS
        distancia_sl = self.gamma_cfg.GAMMA_TRAILING_DIST_PCT # 1.5%
        
        if side == 'LONG':
            sl_price = entry_price * (1 - distancia_sl)
        else:
            sl_price = entry_price * (1 + distancia_sl)
            
        dist_sl = abs(entry_price - sl_price)
        if dist_sl == 0: return None
        
        # Cálculo de Lote (Qty) con el riesgo ajustado
        qty_total = risk_usd / dist_sl
        
        # Validar notional mínimo de Binance ($10 USD de valor nominal)
        # Ajuste de precisión (Asumimos 1 decimal para AAVE, esto podría parametrizarse)
        qty_total = round(qty_total, 1)
        
        if (qty_total * entry_price) < 10.0: 
            return None

        # Construcción del PLAN
        plan = {
            'strategy': 'SCALPING_GAMMA',
            'symbol': self.cfg.SYMBOL, # Añadido explícitamente
            'side': side,
            'qty': qty_total,
            'entry_price': entry_price,
            'sl_price': sl_price,
            
            # INSTRUCCIÓN CLAVE PARA EL CONTRALOR:
            # Le dice que debe aplicar custodia dinámica si está habilitada
            'management_type': 'DYNAMIC_TRAILING' if self.gamma_cfg.GAMMA_TRAILING_ENABLED else 'STATIC',
            
            'tp_hard_price': 0.0, # Se calcula abajo
            'tps': [] # Sin TPs parciales fijos, usamos Trailing
        }
        
        # Cálculo del Hard TP (Techo de seguridad 5%)
        tp_pct = self.gamma_cfg.GAMMA_HARD_TP_PCT
        if side == 'LONG':
            plan['tp_hard_price'] = entry_price * (1 + tp_pct)
        else:
            plan['tp_hard_price'] = entry_price * (1 - tp_pct)
        
        # Logueamos si hubo ajuste de capital
        nota_capital = ""
        if risk_usd < risk_target:
            nota_capital = f"(Ajustado por saldo bajo: ${risk_usd:.2f})"
            
        self.log.registrar_actividad("SHOOTER", f"🎯 GAMMA PLAN REFINADO: {side} @ {entry_price:.2f}. Qty: {qty_total:.3f} {nota_capital}")
        return plan

    def _plan_sniper(self, signal):
        """
        Planificación para Sniper (Swing Trading - Lógica Original Preservada)
        """
        entry_price = signal['price']
        side = signal['side']
        
        balance_disponible = self.fin.get_balance_total()
        risk_target = balance_disponible * self.sniper_cfg.RISK_PER_TRADE
        
        if risk_target < 10.0: return None
        
        sl_pct = self.sniper_cfg.STOP_LOSS_PCT
        if side == 'LONG':
            sl_price = entry_price * (1 - sl_pct)
        else:
            sl_price = entry_price * (1 + sl_pct)
            
        dist_sl = abs(entry_price - sl_price)
        if dist_sl == 0: return None
        
        qty_total = risk_target / dist_sl
        qty_total = round(qty_total, 1) # Redondeo estándar
        
        if (qty_total * entry_price) < 10.0: return None

        tps_final = []
        for nivel in self.sniper_cfg.TP_PLAN:
            dist = nivel['dist']
            price_tp = entry_price * (1 + dist) if side == 'LONG' else entry_price * (1 - dist)
            tps_final.append({'price': price_tp, 'qty': qty_total * nivel['qty_pct'], 'move_sl': nivel['move_sl']})

        plan = {
            'strategy': signal['strategy'],
            'symbol': self.cfg.SYMBOL,
            'side': side,
            'qty': qty_total,
            'entry_price': entry_price,
            'sl_price': sl_price,
            'management_type': 'STATIC_SNIPER', # Distinción importante
            'tps': tps_final
        }
        self.log.registrar_actividad("SHOOTER", f"🎯 SNIPER PLAN: {side} @ {entry_price:.2f}. Qty: {qty_total:.3f}")
        return plan