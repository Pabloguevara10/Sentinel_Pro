# =============================================================================
# UBICACIÓN: execution/comptroller.py
# DESCRIPCIÓN: CONTRALOR TRÍADA V17.8 (CUSTODIA ACTIVA + ORDER MANAGER LINK)
# =============================================================================

from config.config import Config
# Se asume SystemLogger disponible en logs
try:
    from logs.system_logger import SystemLogger
except ImportError:
    SystemLogger = None

class Comptroller:
    """
    CONTRALOR V17.8:
    - Custodia las posiciones abiertas.
    - Ejecuta Trailing Stop (Gamma).
    - Ejecuta Tomas Parciales (Swing).
    - Verifica SL en memoria local (Seguridad).
    """
    def __init__(self, config, order_manager, financials, logger):
        self.cfg = config
        self.om = order_manager
        self.fin = financials
        self.log = logger
        self.posiciones_activas = {} 

    def aceptar_custodia(self, paquete_orden):
        """Registra la orden recién ejecutada para monitoreo."""
        symbol = paquete_orden['symbol']
        
        # Inicializar métricas de monitoreo
        paquete_orden['max_price'] = paquete_orden['entry_price'] 
        paquete_orden['min_price'] = paquete_orden['entry_price']
        paquete_orden['tp1_hit'] = False
        
        # Clave única en diccionario local (por Symbol, asumiendo Hedge maneja IDs internos)
        # Nota: En Hedge Mode puede haber LONG y SHORT a la vez.
        # Usamos ID único compuesto: SYMBOL_SIDE
        key = f"{symbol}_{paquete_orden['side']}"
        self.posiciones_activas[key] = paquete_orden
        
        if self.log:
            self.log.registrar_actividad("COMP", f"🛡️ Custodia iniciada: {key}")

    def auditar_posiciones(self, current_price):
        """
        Ciclo principal de revisión. Se llama cada tick (o cada ciclo rápido).
        """
        if not self.posiciones_activas: return

        # Iteramos sobre una copia para poder modificar el dict original
        for key, pos in list(self.posiciones_activas.items()):
            pos['current_price'] = current_price
            side = pos['side']
            entry = float(pos['entry_price'])
            
            # 1. Actualizar Picos (High/Low desde entrada)
            if current_price > pos['max_price']: pos['max_price'] = current_price
            if current_price < pos['min_price']: pos['min_price'] = current_price
            
            # 2. Calcular PnL % Actual
            if entry > 0:
                if side == 'LONG': pnl_pct = (current_price - entry) / entry
                else: pnl_pct = (entry - current_price) / entry
            else: pnl_pct = 0.0
            
            pos['pnl_pct'] = pnl_pct

            # 3. VERIFICACIÓN DE SEGURIDAD (SL EXISTE?)
            # Usamos Financials para ver si hay SL activo en Binance/Memoria
            tiene_sl, sl_price_real, _ = self.fin.verificar_si_tiene_sl_local(side)
            
            # Sincronizamos nuestro registro con la realidad
            if tiene_sl:
                pos['sl_price'] = sl_price_real
            else:
                # Si no tiene SL, es crítico (excepto si acabamos de abrir y OM está en ello)
                # Aquí podríamos poner lógica de emergencia
                pass

            # 4. GESTIÓN ESTRATÉGICA (ROUTING)
            strategy = pos.get('strategy', 'MANUAL')
            
            if strategy == 'GAMMA':
                self._gestion_gamma(pos, current_price, pnl_pct)
            elif strategy == 'SWING':
                self._gestion_swing(pos, current_price, pnl_pct)
            elif strategy == 'SHADOW':
                # Shadow usa lógica compleja de bandas, aquí simplificamos a seguridad
                # O podríamos implementar trailing básico
                pass
            
            # Verificar si la posición se cerró externamente (limpieza)
            # Esto se hace idealmente en sincronizar_con_exchange, pero aquí podemos chequear qty
            # Si qty llega a 0 en memoria, borrar.

    def _gestion_gamma(self, pos, curr, pnl_pct):
        """Lógica: Trailing Stop Dinámico (Simulador: Activación 1.5%, Dist 0.5%)"""
        cfg = self.cfg.GammaConfig
        
        # Sólo si estamos ganando más que la activación
        if pnl_pct > cfg.TRAILING_ACTIVATION:
            
            # Calcular nuevo SL propuesto
            if pos['side'] == 'LONG':
                nuevo_sl = curr * (1 - cfg.TRAILING_OFFSET)
                # Solo actualizar si sube el SL (proteger ganancia)
                if nuevo_sl > pos['sl_price']:
                    self._mover_sl(pos, nuevo_sl)
            else: # SHORT
                nuevo_sl = curr * (1 + cfg.TRAILING_OFFSET)
                # Solo actualizar si baja el SL
                if nuevo_sl < pos['sl_price'] or pos['sl_price'] == 0:
                     self._mover_sl(pos, nuevo_sl)

    def _gestion_swing(self, pos, curr, pnl_pct):
        """Lógica: Toma Parcial (TP1) y Break Even."""
        cfg = self.cfg.SwingConfig
        
        # Chequear TP1
        if not pos['tp1_hit'] and pnl_pct >= cfg.TP1_DIST:
            # 1. Cerrar Parcial
            qty_total = float(pos['qty'])
            qty_close = qty_total * cfg.TP1_QTY_PCT
            
            if self.log: self.log.registrar_actividad("COMP", f"⭐ TP1 SWING alcanzado. Cerrando {qty_close:.3f}")
            
            if self.om.reducir_posicion(pos['symbol'], qty_close, "TP1_SWING"):
                pos['qty'] -= qty_close
                pos['tp1_hit'] = True
                
                # 2. Mover SL a Break Even (Entrada)
                self._mover_sl(pos, pos['entry_price'])

    def _mover_sl(self, pos, nuevo_precio):
        """Wrapper seguro para mover SL a través de OrderManager."""
        # Filtro de ruido: no mover si la diferencia es mínima (< 0.1%)
        if abs(nuevo_precio - pos['sl_price']) / pos['sl_price'] < 0.001:
            return

        exito = self.om.actualizar_stop_loss(pos['symbol'], pos['side'], nuevo_precio)
        if exito:
            pos['sl_price'] = nuevo_precio
            if self.log: self.log.registrar_actividad("COMP", f"🛡️ Trailing/BE ajustado a {nuevo_precio:.2f}")

    def sincronizar_con_exchange(self):
        """
        Sincroniza la memoria del Comptroller con las posiciones reales reportadas por Financials.
        Si una posición desaparece de Financials (se cerró), la borramos de aquí.
        """
        try:
            real_positions = self.fin.obtener_posiciones_activas_simple()
            # real_positions es lista de dicts
            
            # Crear set de claves reales
            real_keys = set()
            for p in real_positions:
                key = f"{p['symbol']}_{p['side']}"
                real_keys.add(key)
                
                # Si no la tenemos en custodia, ADOPTAR (Manual o reinicio)
                if key not in self.posiciones_activas:
                    if self.log: self.log.registrar_actividad("COMP", f"🕵️ Adoptando huérfana: {key}")
                    self.posiciones_activas[key] = {
                        'symbol': p['symbol'], 'side': p['side'],
                        'qty': p['qty'], 'entry_price': p['entry_price'],
                        'max_price': p['entry_price'], 'min_price': p['entry_price'],
                        'sl_price': 0, 'strategy': 'ADOPTED',
                        'tp1_hit': False
                    }

            # Limpiar posiciones que ya no existen en el exchange
            keys_to_delete = []
            for k in self.posiciones_activas:
                if k not in real_keys:
                    keys_to_delete.append(k)
            
            for k in keys_to_delete:
                del self.posiciones_activas[k]
                if self.log: self.log.registrar_actividad("COMP", f"🏳️ Posición cerrada/liquidada: {k}")
                
        except Exception as e:
            if self.log: self.log.registrar_error("COMP", f"Error Sync: {e}")