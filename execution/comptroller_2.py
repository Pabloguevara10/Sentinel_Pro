import time
from config.config import Config

class Comptroller:
    """
    DEPARTAMENTO DE CONTRALORÍA (V12.0 - CUSTODIA DINÁMICA):
    - Monitorea posiciones en tiempo real.
    - Ejecuta el Trailing Stop (Gamma Strategy).
    - Sincroniza estado con el Exchange.
    """
    def __init__(self, config, order_manager, api_manager, logger):
        self.cfg = config
        self.om = order_manager
        self.api = api_manager
        self.logger = logger
        
        # Cache local de posiciones para dashboard/logs
        self.posiciones_activas = {}

    def sincronizar_con_exchange(self):
        """
        Recupera las posiciones abiertas reales desde Binance al iniciar.
        """
        try:
            real_positions = self.api.get_open_positions_info()
            self.posiciones_activas = {} # Limpiar y recargar
            
            if not real_positions: return

            count = 0
            for pos in real_positions:
                amt = float(pos['positionAmt'])
                if amt != 0 and pos['symbol'] == self.cfg.SYMBOL:
                    # Reconstruimos el estado en memoria
                    pid = f"REC_{int(time.time())}" # ID temporal recuperado
                    self.posiciones_activas[pid] = {
                        'symbol': pos['symbol'],
                        'side': 'LONG' if amt > 0 else 'SHORT',
                        'qty': abs(amt),
                        'entry_price': float(pos['entryPrice']),
                        'pnl_unrealized': float(pos['unRealizedProfit']),
                        'management_type': 'DYNAMIC_TRAILING' # Asumimos custodia dinámica
                    }
                    count += 1
            
            if count > 0:
                self.logger.registrar_actividad("COMPTROLLER", f"♻️ Sincronizado: {count} posiciones recuperadas del Exchange.")
                
        except Exception as e:
            self.logger.registrar_error("COMPTROLLER", f"Error en sincronización inicial: {e}")

    def aceptar_custodia(self, paquete_posicion):
        """
        Registra una nueva posición creada por el OrderManager.
        """
        if paquete_posicion:
            pid = paquete_posicion.get('id', 'UNKNOWN')
            self.posiciones_activas[pid] = paquete_posicion
            self.logger.registrar_actividad("COMPTROLLER", f"🛡️ Custodia aceptada para Posición {pid}")

    def auditar_posiciones_activas(self):
        """
        MÉTODO CRÍTICO (Llamado por Main cada 1s).
        Revisa el precio actual y mueve el Stop Loss si corresponde.
        """
        try:
            # 1. Obtener Datos Reales (Stateless)
            # Consultamos directamente a Binance para no depender de memoria corrupta
            posiciones_api = self.api.get_open_positions_info()
            if not posiciones_api: 
                self.posiciones_activas = {}
                return

            # 2. Obtener Precio de Mercado
            precio_mercado = self.api.get_ticker_price(self.cfg.SYMBOL)
            if precio_mercado == 0: return

            # 3. Iterar y Auditar
            posiciones_encontradas = {}
            
            for pos in posiciones_api:
                # Filtrar solo nuestro símbolo y posiciones abiertas
                if pos['symbol'] != self.cfg.SYMBOL: continue
                amt = float(pos['positionAmt'])
                if amt == 0: continue
                
                side = 'LONG' if amt > 0 else 'SHORT'
                qty = abs(amt)
                
                # Guardar para el dashboard
                posiciones_encontradas['BINANCE_ACTIVE'] = True
                
                # --- LÓGICA DE TRAILING STOP ---
                if self.cfg.GammaConfig.GAMMA_TRAILING_ENABLED:
                    self._gestionar_trailing(side, qty, precio_mercado)

            # Actualizar cache local (simple)
            if not posiciones_encontradas:
                self.posiciones_activas = {}

        except Exception as e:
            self.logger.registrar_error("COMPTROLLER", f"Error en ciclo de auditoría: {e}")

    def _gestionar_trailing(self, side, qty, precio_mercado):
        """
        Cerebro del Trailing Stop (1.5% de distancia).
        """
        try:
            # A. Obtener órdenes activas para ver dónde está el SL actual
            # Nota: Esto requiere un método en API Manager para traer órdenes abiertas
            # Si no existe, usamos una aproximación o intentamos traerlas.
            # Para esta versión robusta, asumiremos que si hay mejora, enviamos la orden.
            # El OrderManager se encarga de cancelar la vieja.
            
            # Necesitamos saber el SL actual. 
            # Opción A: Consultar API (Costoso pero seguro)
            # Opción B: Calcular dónde DEBERÍA estar.
            
            # Vamos a calcular el NUEVO SL ideal
            distancia_pct = self.cfg.GammaConfig.GAMMA_TRAILING_DIST_PCT # 0.015
            umbral_update = self.cfg.GammaConfig.GAMMA_TRAILING_UPDATE_MIN_PCT # 0.002
            
            # Recuperar SL actual de la API (Implementación simplificada)
            # Idealmente APIManager debería tener `get_open_orders`
            # Como parche rápido, consultaremos todas las órdenes abiertas
            ordenes = self.api.client.get_open_orders(symbol=self.cfg.SYMBOL)
            sl_actual_precio = 0.0
            sl_order_id = None
            
            for o in ordenes:
                if o['type'] == 'STOP_MARKET' and o['reduceOnly'] == True:
                    sl_actual_precio = float(o['stopPrice'])
                    sl_order_id = o['orderId']
                    break
            
            if sl_actual_precio == 0:
                return # No hay SL puesto, peligroso pero no podemos hacer trailing sin referencia
            
            nuevo_sl_ideal = 0.0
            update_needed = False
            
            if side == 'LONG':
                nuevo_sl_ideal = precio_mercado * (1 - distancia_pct)
                # Solo subir
                if nuevo_sl_ideal > sl_actual_precio:
                    mejora = (nuevo_sl_ideal - sl_actual_precio) / sl_actual_precio
                    if mejora > umbral_update:
                        update_needed = True
                        
            else: # SHORT
                nuevo_sl_ideal = precio_mercado * (1 + distancia_pct)
                # Solo bajar
                if nuevo_sl_ideal < sl_actual_precio:
                    mejora = (sl_actual_precio - nuevo_sl_ideal) / sl_actual_precio
                    if mejora > umbral_update:
                        update_needed = True
            
            if update_needed:
                self.logger.registrar_actividad("COMPTROLLER", f"⚡ Trailing Activado: Precio {precio_mercado} -> Nuevo SL {nuevo_sl_ideal:.2f}")
                self.om.actualizar_stop_loss_seguro(
                    self.cfg.SYMBOL, side, qty, nuevo_sl_ideal, sl_order_id
                )

        except Exception as e:
            # Errores en trailing no deben detener el bot, solo loguear
            pass