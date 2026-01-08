import time
import os
import sys

# Aseguramos que Python encuentre las carpetas del proyecto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from connections.api_manager import APIManager
from execution.order_manager import OrderManager
from core.financials import Financials 
from data.historical_manager import HistoricalManager

# Logger simplificado para pruebas
class TestLogger:
    def registrar_actividad(self, mod, msg): print(f"✅ [{mod}] {msg}")
    def registrar_error(self, mod, msg, critico=False): print(f"❌ [{mod}] {msg}")
    def advertencia(self, msg): print(f"⚠️ {msg}")
    def log_info(self, msg): self.registrar_actividad("TESTER", msg)
    def log_error(self, msg): self.registrar_error("TESTER", msg)

def main():
    print("==========================================")
    print("🛡️ SENTINEL PRO: PROTOCOLO DE VALIDACIÓN 🛡️")
    print("==========================================")
    
    logger = TestLogger()
    
    # SIN TRY-EXCEPT GLOBAL PARA VER ERRORES REALES
    # 1. INICIALIZACIÓN
    print("\n⏳ Conectando a Binance...")
    api = APIManager(logger)
    fin = Financials(Config, api)
    
    # 2. VALIDACIÓN DE DATOS
    print("\n[1/3] 📡 Verificando Datos Históricos...")
    hist = HistoricalManager(api, logger)
    hist.sincronizar_infraestructura_datos()
    
    # 3. PREPARACIÓN EJECUCIÓN
    print("\n[2/3] ⚙️ Inicializando Order Manager...")
    om = OrderManager(Config, api, logger, fin)
    fin.sincronizar_libro_con_api()
    
    current_symbol = Config.SYMBOL
    print(f"      (Min Qty detectada para {current_symbol}: {om.min_qty})")
    
    while True:
        print("\n------------------------------------------")
        balance = fin.get_balance_total()
        print(f"ACTIVO: {current_symbol} | SALDO: {balance:.2f} USDT")
        print("------------------------------------------")
        print("1. [REQ 3-4]  Abrir LONG (MARKET -> SL -> Registro)")
        print("2. [REQ 3-4]  Abrir SHORT (MARKET -> SL -> Registro)")
        print("3. [REQ 7]    Mover Stop Loss (Modificar Orden)")
        print("4. [REQ 8-9]  Cancelar Orden Específica (Por ID)")
        print("5. [REQ 11]   Consultar Libro de Órdenes (LOCAL)")
        print("6. [REQ 10]   CERRAR POSICIÓN (Pánico)")
        print("X. Salir")
        
        op = input("\n👉 Acción: ").upper().strip()
        
        if op == 'X': break
        
        # --- ABRIR POSICIONES ---
        if op in ['1', '2']:
            side = 'LONG' if op == '1' else 'SHORT'
            price = api.get_ticker_price(current_symbol)
            
            if price == 0:
                print("❌ Error de precio (API no responde).")
                continue
            
            sl_price = price * 0.995 if side == 'LONG' else price * 1.005
            
            plan = {
                'symbol': current_symbol,
                'side': side,
                'qty': om.min_qty, 
                'entry_price': price,
                'sl_price': sl_price,
                'strategy': 'TEST_PROTOCOL',
                'mode': 'HEDGE',
                'type': 'MARKET'
            }
            
            print(f"🚀 Enviando orden {side} a MARKET...")
            exito, paquete = om.ejecutar_estrategia(plan)
            
            if exito:
                print(f"✨ ¡ÉXITO! Posición abierta y protegida.")
                print(f"   SL ID: {paquete.get('sl_order_id')}")
            else:
                print("⚠️ FALLO EN EJECUCIÓN. Revisa el log de error arriba.")

        # --- MOVER SL ---
        elif op == '3':
            ids_sl = [k for k, v in fin.libro_ordenes_local.items() if v['type'] in ['STOP_MARKET', 'STOP']]
            
            if not ids_sl:
                print("⚠️ No hay Stop Loss registrados en el libro local.")
                continue
                
            print(f"IDs Disponibles: {ids_sl}")
            old_id = ids_sl[0]
            order_data = fin.libro_ordenes_local[old_id]
            
            stop_actual = order_data.get('stopPrice', order_data.get('activationPrice', '0'))
            print(f"SL Actual: {stop_actual}")
            
            try:
                input_precio = input(f"Nuevo precio para SL? ")
                if input_precio:
                    nuevo_precio = float(input_precio)
                    res = om.actualizar_stop_loss(current_symbol, order_data['positionSide'], nuevo_precio)
                    if res: print("✅ SL Actualizado correctamente.")
                    else: print("❌ Falló la actualización del SL.")
            except ValueError:
                print("❌ Entrada inválida")

        # --- CANCELAR ORDEN ---
        elif op == '4':
            print("Libro actual:", list(fin.libro_ordenes_local.keys()))
            target_id = input("ID a cancelar: ").strip()
            
            if target_id in fin.libro_ordenes_local:
                om.cancelar_orden_especifica(current_symbol, target_id, "TEST_USER")
            else:
                print("❌ Ese ID no está en el libro local.")

        # --- CONSULTAR BITÁCORA ---
        elif op == '5':
            libro = om.consultar_libro_local()
            if not libro:
                print("📭 Libro Local Vacío.")
            else:
                print(f"📚 LIBRO LOCAL ({len(libro)} órdenes activas):")
                for oid, data in libro.items():
                    tipo = data.get('type', 'UNKNOWN')
                    lado = data.get('side', 'UNKNOWN')
                    precio = data.get('stopPrice', data.get('price', 'MARKET'))
                    print(f"   - ID: {oid} | {lado} | {tipo} | Precio: {precio}")

        # --- CERRAR TODO ---
        elif op == '6':
            res = om.cerrar_posicion(current_symbol, "TEST_PANIC")
            if res: print("✅ Posición cerrada con éxito.")
            else: print("⚠️ No se pudo cerrar la posición (¿Posición vacía o error API?)")

if __name__ == "__main__":
    main()