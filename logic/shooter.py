from config.config import Config

class Shooter:
    """
    DEPARTAMENTO DE ESTRATEGIA (Gestión de Riesgo V10):
    Implementa la gestión de capital 'High Stakes' del perfil Sniper.
    Lee configuración dinámica desde Config.SniperConfig.
    """
    def __init__(self, config, logger):
        self.cfg = config
        self.log = logger
        # Cargamos perfil Sniper
        self.sniper_cfg = self.cfg.SniperConfig

    def validar_y_crear_plan(self, signal, open_positions_count):
        # 1. Filtro de Saturación (Máx 2 posiciones simultáneas)
        if open_positions_count >= 2:
            return None

        # 2. Datos de Mercado
        entry_price = signal['price']
        side = signal['side']
        
        # 3. Cálculo de Riesgo (High Stakes)
        # Asumimos capital base $1000 si no hay lectura, o implementar lectura de Financials aquí
        capital_base = 1000.0 
        risk_usd = capital_base * self.sniper_cfg.RISK_PER_TRADE
        
        # 4. Cálculo de Stop Loss
        sl_pct = self.sniper_cfg.STOP_LOSS_PCT
        if side == 'LONG':
            sl_price = entry_price * (1 - sl_pct)
        else:
            sl_price = entry_price * (1 + sl_pct)
            
        dist_sl = abs(entry_price - sl_price)
        if dist_sl == 0: return None
        
        # 5. Tamaño de Posición
        qty_total = risk_usd / dist_sl
        
        # Filtro de lote mínimo ($10 USD notional)
        if (qty_total * entry_price) < 10.0:
            return None

        # 6. Construcción de TPs Escalonados
        tps_final = []
        for nivel in self.sniper_cfg.TP_PLAN:
            dist = nivel['dist']
            qty_pct = nivel['qty_pct']
            
            if side == 'LONG':
                price_tp = entry_price * (1 + dist)
            else:
                price_tp = entry_price * (1 - dist)
                
            qty_tp = qty_total * qty_pct
            
            tps_final.append({
                'price': price_tp,
                'qty': qty_tp,
                'move_sl': nivel['move_sl'] # Esta info la usará el Contralor en el futuro
            })

        # 7. Plan Maestro
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