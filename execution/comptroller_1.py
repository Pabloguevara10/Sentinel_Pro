import time
from config.config import Config

class Comptroller:
    """
    CONTRALOR HÍBRIDO (V14.2 - ZERO CRASH FIX):
    - Custodia de Posiciones.
    - Adopción de Huérfanos.
    - Gestión Dual: Trailing (Gamma) y Fraccionada (Swing).
    - Protección contra errores de división por cero.
    """
    def __init__(self, config, order_manager, financials, logger):
        self.cfg = config
        self.om = order_manager
        self.fin = financials
        self.log = logger
        self.posiciones_activas = {} # { 'AAVEUSDT': { ...datos_plan... } }

    def aceptar_custodia(self, paquete_orden):
        """
        Recibe una orden recién ejecutada por el OrderManager y la guarda en memoria.
        """
        symbol = paquete_orden['symbol']
        # Inicializamos banderas de gestión
        paquete_orden['tp1_hit'] = False
        paquete_orden['tp2_hit'] = False
        paquete_orden['max_price'] = paquete_orden['entry_price'] 
        
        self.posiciones_activas[symbol] = paquete_orden
        self.log.registrar_actividad("COMPTROLLER", f"🛡️ Custodia iniciada: {symbol}")

    def auditar_posiciones(self, current_price, rsi_15m=50.0):
        """
        Latido cardíaco del bot. Revisa si hay que mover SL, cerrar parciales o cerrar todo.
        """
        if not self.posiciones_activas: return

        # Iteramos sobre una copia para poder modificar el diccionario original si es necesario
        for symbol, pos in list(self.posiciones_activas.items()):
            
            # 1. Actualizar Datos de Mercado en la Ficha
            pos['current_price'] = current_price
            
            # Actualizar Pico Máximo (High Watermark) para trailing
            if pos['side'] == 'LONG':
                if current_price > pos['max_price']: pos['max_price'] = current_price
            else:
                if current_price < pos['max_price']: pos['max_price'] = current_price
            
            # 2. Calcular PnL No Realizado (%)
            entry = float(pos['entry_price'])
            
            # PROTECCIÓN: Si el precio de entrada es 0 o inválido, saltamos para evitar errores
            if entry <= 0: continue
            
            if pos['side'] == 'LONG':
                pnl_pct = (current_price - entry) / entry
            else:
                pnl_pct = (entry - current_price) / entry
                
            pos['pnl_pct'] = pnl_pct
            
            # 3. Enrutamiento de Gestión (Router)
            mgmt_type = pos.get('management_type', 'STATIC')
            
            # GESTIÓN GAMMA / RECOVERY (Trailing Stop)
            if mgmt_type == 'DYNAMIC_TRAILING' or mgmt_type == 'ADOPTED_RECOVERY':
                self._gestion_dynamic_trailing(pos, current_price, pnl_pct)
                
            # GESTIÓN SWING (Parciales + BE)
            elif mgmt_type == 'FRACTIONAL_SWING':
                self._gestion_fractional_swing(pos, current_price, pnl_pct)

    def _gestion_dynamic_trailing(self, pos, current_price, pnl_pct):
        """Lógica Gamma: Trailing Stop agresivo."""
        
        # PROTECCIÓN CRÍTICA: Si el SL es 0 (por fallo de colocación), salimos para no dividir por cero
        if float(pos.get('sl_price', 0)) <= 0: return

        params = pos.get('params')
        if not params: params = self.cfg.GammaConfig

        # A. Hard TP Check (Seguridad adicional)
        tp_hard = pos.get('tp_hard_price', 0)
        if tp_hard > 0:
            if (pos['side'] == 'LONG' and current_price >= tp_hard) or \
               (pos['side'] == 'SHORT' and current_price <= tp_hard):
                self.log.registrar_actividad("COMPTROLLER", f"💰 Hard TP Gamma alcanzado. Cerrando {pos['symbol']}.")
                self.om.cerrar_posicion(pos['symbol'], "HARD_TP_GAMMA")
                if pos['symbol'] in self.posiciones_activas:
                    del self.posiciones_activas[pos['symbol']]
                return

        # B. Trailing Logic
        dist_trail = params.GAMMA_TRAILING_DIST_PCT
        new_sl = 0.0
        
        if pos['side'] == 'LONG':
            propuesto = current_price * (1 - dist_trail)
            if propuesto > pos['sl_price']: new_sl = propuesto
        else:
            propuesto = current_price * (1 + dist_trail)
            if propuesto < pos['sl_price']: new_sl = propuesto
                
        # Ejecución del movimiento
        if new_sl > 0:
            # Doble chequeo anti-cero antes de la división
            if pos['sl_price'] <= 0: return

            umb_update = getattr(params, 'GAMMA_TRAILING_UPDATE_MIN_PCT', 0.001)
            diff = abs(new_sl - pos['sl_price']) / pos['sl_price']
            
            if diff >= umb_update:
                exito = self.om.actualizar_stop_loss(pos['symbol'], new_sl)
                if exito:
                    pos['sl_price'] = new_sl

    def _gestion_fractional_swing(self, pos, current_price, pnl_pct):
        """Lógica Swing: Tomas parciales y Protección de Capital."""
        params = pos.get('params')
        if not params: return
        
        # 1. TP1 (Primer Objetivo)
        if not pos['tp1_hit'] and pnl_pct >= params.TP1_DIST:
            self.log.registrar_actividad("COMPTROLLER", f"⭐ TP1 Swing Alcanzado (+{pnl_pct:.2%}).")
            
            qty_to_close = pos['qty'] * params.TP1_QTY 
            # Reducir posición
            if self.om.reducir_posicion(pos['symbol'], qty_to_close, "TP1_SWING"):
                pos['qty'] -= qty_to_close
                pos['tp1_hit'] = True
                
                # Mover a Breakeven
                buffer = pos['entry_price'] * 0.001 
                new_sl = pos['entry_price'] + buffer if pos['side'] == 'LONG' else pos['entry_price'] - buffer
                
                if self.om.actualizar_stop_loss(pos['symbol'], new_sl):
                    pos['sl_price'] = new_sl

        # 2. TP2 (Segundo Objetivo)
        elif not pos['tp2_hit'] and pnl_pct >= params.TP2_DIST:
            self.log.registrar_actividad("COMPTROLLER", f"🌟 TP2 Swing Alcanzado (+{pnl_pct:.2%}).")
            
            qty_to_close = pos['qty'] * params.TP2_QTY 
            if self.om.reducir_posicion(pos['symbol'], qty_to_close, "TP2_SWING"):
                pos['qty'] -= qty_to_close
                pos['tp2_hit'] = True
                
                # Mover SL al nivel del TP1 (Lock Profit)
                tp1_level = pos['entry_price'] * (1 + params.TP1_DIST) if pos['side'] == 'LONG' \
                            else pos['entry_price'] * (1 - params.TP1_DIST)
                
                if self.om.actualizar_stop_loss(pos['symbol'], tp1_level):
                    pos['sl_price'] = tp1_level

    def sincronizar_con_exchange(self):
        """
        Sincronización Inteligente:
        1. Elimina posiciones fantasmas (En memoria pero no en Binance).
        2. ADOPTA posiciones huérfanas y verifica su protección (SL).
        """
        try:
            posiciones_reales = self.fin.obtener_posiciones_activas_simple()
            simbolos_reales = [p['symbol'] for p in posiciones_reales]
            
            # 1. Limpieza (Garbage Collection)
            for symbol in list(self.posiciones_activas.keys()):
                if symbol not in simbolos_reales:
                    self.log.registrar_actividad("COMPTROLLER", f"⚠️ Posición {symbol} cerrada externamente. Limpiando memoria.")
                    del self.posiciones_activas[symbol]

            # 2. Adopción y Verificación (Protocolo de Seguridad)
            for p in posiciones_reales:
                sym = p['symbol']
                
                # Si es nueva para el bot (Huérfana)
                if sym not in self.posiciones_activas:
                    self.log.registrar_actividad("COMPTROLLER", f"🕵️ Adoptando {sym}. Verificando blindaje...")
                    
                    # VERIFICACIÓN DE SL REAL EN BINANCE
                    tiene_sl_real = False
                    current_sl_price = 0.0
                    
                    try:
                        open_orders = self.fin.api.client.get_open_orders(symbol=sym)
                        for o in open_orders:
                            if o['type'] == 'STOP_MARKET':
                                tiene_sl_real = True
                                current_sl_price = float(o['stopPrice'])
                                break
                    except Exception as e:
                        self.log.registrar_error("COMPTROLLER", f"Error verificando SL de {sym}: {e}")

                    # Si no tiene SL, crearlo de EMERGENCIA
                    if not tiene_sl_real:
                        self.log.registrar_error("COMPTROLLER", f"⚠️ {sym} está DESPROTEGIDA. Creando SL de Emergencia.")
                        entry = p['entry_price']
                        side = p['side']
                        qty = p['qty']
                        # SL al 10% de distancia por seguridad
                        sl_price = entry * 0.9 if side == 'LONG' else entry * 1.1
                        
                        # Usamos método interno de OM para colocarlo directo
                        if self.om._colocar_stop_loss_orden(sym, side, sl_price, qty):
                            current_sl_price = sl_price
                            self.log.registrar_actividad("COMPTROLLER", "🛡️ SL de Emergencia colocado.")
                    
                    # Registrar en memoria
                    ficha_adoptada = {
                        'symbol': sym,
                        'strategy': 'MANUAL_RECOVERY',
                        'side': p['side'],
                        'qty': p['qty'],
                        'entry_price': p['entry_price'],
                        'sl_price': current_sl_price,
                        'current_price': p['entry_price'],
                        'max_price': p['entry_price'],
                        'management_type': 'ADOPTED_RECOVERY', # Activa el trailing
                        'params': self.cfg.GammaConfig
                    }
                    self.posiciones_activas[sym] = ficha_adoptada
                    self.log.registrar_actividad("COMPTROLLER", f"✅ Posición {sym} adoptada y asegurada.")
                    
        except Exception as e:
            self.log.registrar_error("COMPTROLLER", f"Error en Sincronización: {e}")