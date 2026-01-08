# =============================================================================
# NOMBRE: manual_tester.py
# VERSIÓN: 3.1 (HEDGE MODE PATCH)
# DESCRIPCIÓN: Probador con corrección de parámetros para Hedge Mode.
# =============================================================================

import time
import os
import sys
import logging
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from connections.api_manager import APIManager
from execution.order_manager import OrderManager
from core.financials import Financials 

class ForensicLogger:
    def __init__(self, filename="manual_session.log"):
        self.logger = logging.getLogger("TESTER")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers = [] 
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
        file_handler = logging.FileHandler(filename, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def registrar_actividad(self, mod, msg): self.logger.info(f"[{mod}] {msg}")
    def registrar_error(self, mod, msg): self.logger.error(f"[{mod}] {msg}")

def main():
    logger = ForensicLogger()
    logger.registrar_actividad("INIT", "="*50)
    logger.registrar_actividad("INIT", "🛡️ CONSOLA DE DIAGNÓSTICO V3.1 (HEDGE PATCH) 🛡️")
    
    try:
        api = APIManager(logger)
        fin = Financials(Config, api)
        om = OrderManager(Config, api, logger, fin)
        symbol = Config.SYMBOL
        logger.registrar_actividad("CALIB", f"Par: {symbol} | Qty Prec: {om.qty_precision} | Price Prec: {om.price_precision}")
    except Exception as e:
        logger.registrar_error("INIT", f"Error crítico: {e}")
        return

    while True:
        print("\n" + "="*40)
        print(f"   MANDO MANUAL - {symbol} (HEDGE)")
        print("="*40)
        print("1. 📊 Estado")
        print("2. ⚡ Abrir Posición (MARKET)")
        print("3. 🛡️ Actualizar SL")
        print("4. 🗑️ Cancelar ID")
        print("5. 📚 Libro Local")
        print("6. 🚨 PÁNICO")
        print("7. 🎯 INYECTAR T/P (HEDGE MODE FIX)")
        print("Q. 🚪 Salir")
        
        op = input("\n>> ").strip().upper()
        
        if op == '1':
            price = api.get_ticker_price(symbol)
            pos = om._leer_datos_posicion(symbol)
            logger.registrar_actividad("STATUS", f"Precio: {price}")
            if pos and float(pos['positionAmt']) != 0:
                logger.registrar_actividad("STATUS", f"POSICIÓN: {pos['side']} | Amt: {pos['positionAmt']} | Entry: {pos['entryPrice']}")
            else: logger.registrar_actividad("STATUS", "Sin posición.")

        elif op == '2':
            side_in = input("Lado (L=Long / S=Short)? ").upper()
            usd_in = input("Cantidad USDT? ")
            try:
                side = 'LONG' if side_in == 'L' else 'SHORT'
                margin = float(usd_in)
                price = api.get_ticker_price(symbol)
                qty = (margin * Config.LEVERAGE) / price
                logger.registrar_actividad("CMD", f"Abriendo {side} (${margin})...")
                
                plan = {
                    'symbol': symbol, 'strategy': 'MANUAL', 'side': side,
                    'qty': qty, 'entry_price': price, 'execution_type': 'MARKET',
                    'sl_price': price * 0.98 if side == 'LONG' else price * 1.02
                }
                ok, pack = om.ejecutar_estrategia(plan)
                if ok: logger.registrar_actividad("CMD", "✅ Ejecución OK")
                else: logger.registrar_error("CMD", "❌ Fallo Apertura")
            except Exception as e: logger.registrar_error("CMD", f"Error: {e}")

        elif op == '3':
            new_sl = input("Nuevo SL: ")
            try:
                pos = om._leer_datos_posicion(symbol)
                if pos and float(pos['positionAmt']) != 0:
                    side = 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT'
                    res = om.actualizar_stop_loss(symbol, side, float(new_sl))
                    if res: logger.registrar_actividad("CMD", f"✅ SL OK: {res}")
                else: print("❌ Sin posición.")
            except Exception: pass

        elif op == '4':
            oid = input("ID: ")
            om.cancelar_orden_especifica(symbol, oid)

        elif op == '5':
            print(list(om.consultar_libro_local().keys()))

        elif op == '6': om.cerrar_posicion(symbol, "MANUAL")

        elif op == '7':
            logger.registrar_actividad("TP_TEST", "Protocolo T/P HEDGE MODE...")
            pos = om._leer_datos_posicion(symbol)
            if not pos or float(pos['positionAmt']) == 0:
                logger.registrar_error("TP_TEST", "❌ Abre una posición primero.")
                continue
                
            amt = float(pos['positionAmt'])
            side = 'LONG' if amt > 0 else 'SHORT'
            qty_total = abs(amt)
            
            logger.registrar_actividad("TP_TEST", f"Detectado: {side} | Total: {qty_total}")
            p1 = input("Precio TP1 (40%): ")
            p2 = input("Precio TP2 (30%) [Enter omitir]: ")
            
            # Cálculo Blindado
            q1 = om._blindar_float(qty_total * 0.40, om.qty_precision)
            
            try:
                # --- TP1 CON PARCHE HEDGE ---
                logger.registrar_actividad("TP_TEST", f"Enviando TP1: {q1} @ {p1}...")
                pl1 = om.director.construir_take_profit_limit(symbol, side, q1, float(p1))
                
                # PARCHE: Eliminar reduceOnly y asegurar positionSide
                if 'reduceOnly' in pl1: del pl1['reduceOnly']
                pl1['positionSide'] = side # 'LONG' o 'SHORT'
                
                ok1, res1 = api.execute_generic_order(pl1)
                if ok1: 
                    logger.registrar_actividad("TP_TEST", f"✅ TP1 ACEPTADO ID: {res1['orderId']}")
                    fin.registrar_orden_en_libro(res1)
                else: 
                    logger.registrar_error("TP_TEST", f"❌ RECHAZO TP1: {res1}")

                # --- TP2 CON PARCHE HEDGE ---
                if p2.strip():
                    q2 = om._blindar_float(qty_total * 0.30, om.qty_precision)
                    logger.registrar_actividad("TP_TEST", f"Enviando TP2: {q2} @ {p2}...")
                    pl2 = om.director.construir_take_profit_limit(symbol, side, q2, float(p2))
                    
                    if 'reduceOnly' in pl2: del pl2['reduceOnly']
                    pl2['positionSide'] = side
                    
                    ok2, res2 = api.execute_generic_order(pl2)
                    if ok2: 
                        logger.registrar_actividad("TP_TEST", f"✅ TP2 ACEPTADO ID: {res2['orderId']}")
                        fin.registrar_orden_en_libro(res2)
                    else: 
                        logger.registrar_error("TP_TEST", f"❌ RECHAZO TP2: {res2}")
                        
            except Exception as e: logger.registrar_error("TP_TEST", f"Excepción: {e}")

        elif op == 'Q': break

if __name__ == "__main__":
    main()