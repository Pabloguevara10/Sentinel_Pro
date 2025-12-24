import time
import os
import sys

# Aseguramos que Python encuentre las carpetas del proyecto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from connections.api_manager import APIManager
from execution.order_manager import OrderManager
from core.financials import Financials 

# Configuración Fake para Logger (Para que funcione independiente del Main)
class DummyLogger:
    def registrar_actividad(self, mod, msg): print(f"ℹ️ [{mod}] {msg}")
    def registrar_error(self, mod, msg, critico=False): print(f"❌ [{mod}] {msg}")
    def advertencia(self, msg): print(f"⚠️ {msg}")
    # Alias para compatibilidad con OrderManager V15
    def log_info(self, msg): self.registrar_actividad("TESTER", msg)
    def log_error(self, msg): self.registrar_error("TESTER", msg)

def main():
    print("\n==========================================")
    print("🛡️ PROTOCOLO DE DISPARO MANUAL (TESTER) 🛡️")
    print("==========================================")
    print(f"Modo: {Config.SYSTEM_MODE}")
    print(f"Símbolo: {Config.SYMBOL}")
    print(f"Cantidad Mínima Configurada: {Config.MIN_QTY} AAVE")
    
    logger = DummyLogger()
    
    try:
        # 1. Inicializamos conexiones
        print("\n⏳ Conectando a Binance...")
        api = APIManager(logger)
        
        # 2. Inicializamos Finanzas (Para ver saldo real)
        fin = Financials(Config, api)
        saldo = fin.get_balance_total()
        print(f"💰 Saldo Futuros Detectado: ${saldo:.2f} USDT")
        
        # 3. Inicializamos el Gestor de Órdenes
        om = OrderManager(Config, api, logger)
        
        while True:
            print("\n------------------------------------------")
            print("OPCIONES DE PRUEBA:")
            print(" [L] LONG de Prueba (Mínimo Lotaje)")
            print(" [S] SHORT de Prueba (Mínimo Lotaje)")
            print(" [C] CERRAR Posición (Market)")
            print(" [X] Salir")
            
            choice = input("\n👉 Comando: ").upper().strip()
            
            if choice == 'X': break
            
            if choice == 'L' or choice == 'S':
                side = 'LONG' if choice == 'L' else 'SHORT'
                
                # A. Obtener precio real
                current_price = api.get_ticker_price(Config.SYMBOL)
                if current_price == 0:
                    print("❌ Error: No se pudo obtener precio de mercado.")
                    continue

                # B. Definir SL de seguridad (1%)
                if side == 'LONG': sl_price = current_price * 0.99
                else: sl_price = current_price * 1.01
                
                # C. Crear Plan con MÍNIMA PORCIÓN
                plan = {
                    'symbol': Config.SYMBOL,
                    'side': side,
                    'qty': Config.MIN_QTY, # <--- USA LA CANTIDAD MÍNIMA DEL CONFIG
                    'entry_price': current_price,
                    'sl_price': sl_price,
                    'strategy': 'MANUAL_TEST',
                    'management_type': 'STATIC'
                }
                
                print(f"\n🚀 EJECUTANDO ORDEN {side}...")
                print(f"   Precio: ${current_price}")
                print(f"   Cantidad: {plan['qty']} AAVE")
                print(f"   Stop Loss: ${sl_price:.2f}")
                
                # D. Ejecutar usando el OrderManager real del bot
                exito, res = om.ejecutar_estrategia(plan)
                
                if exito:
                    print("\n✅ ¡ÉXITO! ORDEN COLOCADA EN BINANCE.")
                    print("---------------------------------------")
                    print("👀 Ve a la App de Binance y verifica:")
                    print("   1. Posición Abierta (Pestaña Posiciones).")
                    print("   2. Stop Loss Pendiente (Pestaña Órdenes Abiertas).")
                else:
                    print("\n❌ FALLO. El OrderManager rechazó la orden o Binance dio error.")

            elif choice == 'C':
                print(f"\n🧹 Cerrando posición de {Config.SYMBOL}...")
                om.cerrar_posicion(Config.SYMBOL, "MANUAL_TEST_CLOSE")

    except Exception as e:
        print(f"\n💥 CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()