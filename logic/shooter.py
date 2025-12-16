from config.config import Config

class Shooter:
    """
    DEPARTAMENTO DE ESTRATEGIA (Gestión de Riesgo V11.6):
    - Filtra señales duplicadas (mismo lado y precio cercano).
    - Ajusta el lotaje al capital real disponible (Downsizing).
    """
    def __init__(self, config, logger, financials):
        self.cfg = config
        self.log = logger
        self.fin = financials # Inyección de dependencia financiera
        self.sniper_cfg = self.cfg.SniperConfig

    def validar_y_crear_plan(self, signal, open_positions_dict):
        # 1. FILTRO DE SATURACIÓN (Máx 2 posiciones)
        if len(open_positions_dict) >= 2:
            return None

        # 2. FILTRO DE DUPLICADOS (Anti-Overlap)
        # Si ya tengo un LONG y el precio actual está a < 0.5% del precio de entrada, rechazo.
        current_price = signal['price']
        side = signal['side']
        
        for pos in open_positions_dict.values():
            if pos['side'] == side:
                entry_open = pos['entry_price']
                diff_pct = abs(current_price - entry_open) / entry_open
                if diff_pct < 0.005: # 0.5% de tolerancia
                    self.log.registrar_actividad("SHOOTER", f"⛔ Señal rechazada: Duplicado de posición existente ({diff_pct:.2%})")
                    return None

        # 3. SELECCIÓN DE ESTRATEGIA
        strategy = signal.get('strategy', 'UNKNOWN')
        if strategy == 'SCALPING_GAMMA':
            return self._plan_gamma(signal)
        else:
            return self._plan_sniper(signal)

    def _plan_gamma(self, signal):
        entry_price = signal['price']
        side = signal['side']
        
        # A. DEFINICIÓN DE RIESGO
        # Leemos configuración deseada
        risk_target = getattr(self.cfg.GammaConfig, 'RISK_USD_FIXED', 50.0)
        
        # B. VERIFICACIÓN FINANCIERA (La Variante)
        # Consultamos saldo real disponible
        balance_disponible = self.fin.get_balance_total()
        
        # Ajustamos el riesgo: Usamos lo que haya, hasta el máximo configurado
        risk_usd = min(risk_target, balance_disponible)
        
        # Filtro de pobreza: Si hay menos de $10, no operamos
        if risk_usd < 10.0:
            self.log.registrar_error("SHOOTER", f"Capital insuficiente (${risk_usd:.2f}) para operar Gamma.")
            return None

        # C. CÁLCULOS TÉCNICOS
        sl_pct = 0.015 
        tp1_pct = 0.05 
        
        if side == 'LONG':
            sl_price = entry_price * (1 - sl_pct)
            tp1_price = entry_price * (1 + tp1_pct)
        else:
            sl_price = entry_price * (1 + sl_pct)
            tp1_price = entry_price * (1 - tp1_pct)
            
        dist_sl = abs(entry_price - sl_price)
        if dist_sl == 0: return None
        
        # Cálculo de Lote (Qty) con el riesgo ajustado
        qty_total = risk_usd / dist_sl
        
        # Validar notional mínimo de Binance ($10 USD de valor nominal)
        if (qty_total * entry_price) < 10.0: return None

        tps_final = [{
            'price': tp1_price,
            'qty': qty_total * 0.50,
            'move_sl': True
        }]

        plan = {
            'strategy': 'SCALPING_GAMMA',
            'side': side,
            'qty': qty_total,
            'entry_price': entry_price,
            'sl_price': sl_price,
            'tps': tps_final
        }
        
        # Logueamos si hubo ajuste de capital
        nota_capital = ""
        if risk_usd < risk_target:
            nota_capital = f"(Ajustado por saldo bajo: ${risk_usd:.2f})"
            
        self.log.registrar_actividad("SHOOTER", f"🎯 GAMMA PLAN: {side} @ {entry_price:.2f}. Qty: {qty_total:.3f} {nota_capital}")
        return plan

    def _plan_sniper(self, signal):
        # Lógica Sniper (Simplificada para mantener estructura, también debería validar fondos)
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
        
        if (qty_total * entry_price) < 10.0: return None

        tps_final = []
        for nivel in self.sniper_cfg.TP_PLAN:
            dist = nivel['dist']
            price_tp = entry_price * (1 + dist) if side == 'LONG' else entry_price * (1 - dist)
            tps_final.append({'price': price_tp, 'qty': qty_total * nivel['qty_pct'], 'move_sl': nivel['move_sl']})

        plan = {
            'strategy': signal['strategy'],
            'side': side,
            'qty': qty_total,
            'entry_price': entry_price,
            'sl_price': sl_price,
            'tps': tps_final
        }
        self.log.registrar_actividad("SHOOTER", f"🎯 SNIPER PLAN: {side} @ {entry_price:.2f}. Qty: {qty_total:.3f}")
        return plan