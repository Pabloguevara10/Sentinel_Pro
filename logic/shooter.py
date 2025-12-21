from config.config import Config

class Shooter:
    """
    DEPARTAMENTO DE RIESGO Y PLANIFICACIÓN (V13.1):
    - Calcula lotaje dinámico basado en params V13.
    - Filtra saturación de cupos.
    """
    def __init__(self, config, logger, financials):
        self.cfg = config
        self.log = logger
        self.fin = financials 

    def validar_y_crear_plan(self, signal, open_positions_dict):
        """Orquestador de planes de trading."""
        
        # 1. FILTRO DE SATURACIÓN (Cupos V13)
        total_open = len(open_positions_dict)
        if total_open >= self.cfg.MAX_RISK_SLOTS:
            return None

        # Contar cupos por estrategia
        gamma_count = sum(1 for p in open_positions_dict.values() if 'GAMMA' in p.get('strategy', ''))
        swing_count = sum(1 for p in open_positions_dict.values() if 'SWING' in p.get('strategy', ''))
        
        strat = signal.get('strategy', '')
        if 'GAMMA' in strat and gamma_count >= self.cfg.MAX_GAMMA_SLOTS: return None
        if 'SWING' in strat and swing_count >= self.cfg.MAX_SWING_SLOTS: return None

        # 2. FILTRO DE DUPLICADOS (Anti-Overlap simple)
        for pid, pos in open_positions_dict.items():
            if pos['side'] == signal['side'] and pos['symbol'] == self.cfg.SYMBOL:
                # Si ya estoy dentro en la misma dirección, ignoro (simplificado)
                return None

        # 3. CÁLCULO DE LOTAJE
        # Extraemos la config específica que viene del Brain (GammaConfig o SwingConfig)
        strat_params = signal.get('params') 
        if not strat_params: return None # Error de seguridad
        
        risk_usd = strat_params.RISK_USD_FIXED
        entry_price = signal['price']
        
        # Definir SL % según modo
        mode = signal.get('mode', 'NORMAL')
        if 'GAMMA' in strat:
            sl_pct = strat_params.SL_NORMAL if 'NORMAL' in mode else strat_params.SL_HEDGE
        else: # SWING
            sl_pct = strat_params.SL_INIT_NORMAL if 'NORMAL' in mode else strat_params.SL_INIT_HEDGE
            
        # Calcular Precio SL
        side = signal['side']
        if side == 'LONG': sl_price = entry_price * (1 - sl_pct)
        else: sl_price = entry_price * (1 + sl_pct)
        
        # Calcular Cantidad (Qty)
        # Risk = Qty * Distancia_Precio
        # Pero aquí usamos Margen Fijo (RISK_USD_FIXED) como tamaño de posición nocional aprox
        # Ojo: Si RISK_USD_FIXED es el margen, Qty = Margen / Precio (si apalancamiento es 1x)
        # Si queremos arriesgar X dólares en el SL, la fórmula es: Risk_Amount / (Entry - SL)
        
        # Usaremos modelo de "Inversión Fija" (Margin) por simplicidad y seguridad
        qty = risk_usd / entry_price 
        qty = round(qty, 2) # Ajustar precisión de AAVE (2 decimales usualmente)
        
        if (qty * entry_price) < 6.0: return None # Mínimo Binance ~$5-10
        
        # 4. CONSTRUIR PLAN
        plan = {
            'strategy': strat,
            'mode': mode, # Importante para Comptroller
            'symbol': self.cfg.SYMBOL,
            'side': side,
            'qty': qty,
            'entry_price': entry_price,
            'sl_price': sl_price,
            'params': strat_params # Pasamos params al Comptroller via Plan
        }
        
        return plan