import time
import os
import sys

# Aseguramos que Python encuentre las carpetas del proyecto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from connections.api_manager import APIManager
from execution.order_manager import OrderManager
# Eliminamos la línea de SystemLogger que causaba el error
from core.financials import Financials 

# Configuración Fake para Logger (Para que no falle si falta el real)
class DummyLogger:
    def registrar_actividad(self, mod, msg): print(f"✅ [{mod}] {msg}")
    def registrar_error(self, mod, msg, critico=False): print(f"❌ [{mod}] {msg}")
    def advertencia(self, msg): print(f"⚠️ {msg}")

def main():
    print("==========================================")
    print("🛡️ PROTOCOLO DE VALIDACIÓN MANUAL (HEDGE) 🛡️")
    print("==========================================")
    
    logger = DummyLogger()
    
    try:
        # Inicializamos los módulos
        api = APIManager(logger)
        
        # Intentamos cargar Financials, si falla, usamos saldo dummy
        try:
            fin = Financials(Config, api)
            saldo = fin.get_balance_total()
        except:
            saldo = "No disponible"
            
        om = OrderManager(Config, api, logger)
        
        print(f"\n📡 Conexión establecida. Saldo: {saldo}")
        
        while True:
            print("\n------------------------------------------")
            print("OPCIONES:")
            print(" [L] Abrir LONG (0.1 AAVE) + SL")
            print(" [S] Abrir SHORT (0.1 AAVE) + SL")
            print(" [C] CERRAR TODO (Pánico)")
            print(" [X] Salir")
            
            choice = input("\n👉 Comando: ").upper().strip()
            
            if choice == 'X': break
            
            if choice == 'L' or choice == 'S':
                side = 'LONG' if choice == 'L' else 'SHORT'
                
                # Obtenemos precio actual
                current_price = api.get_ticker_price(Config.SYMBOL)
                if current_price == 0:
                    print("❌ Error: No se pudo obtener precio de mercado.")
                    continue

                # Definir SL al 1% de distancia
                if side == 'LONG': sl_price = current_price * 0.99
                else: sl_price = current_price * 1.01
                
                plan = {
                    'symbol': Config.SYMBOL,
                    'side': side,
                    'qty': 0.1, # Cantidad mínima
                    'entry_price': current_price,
                    'sl_price': sl_price
                }
                
                print(f"\n🚀 EJECUTANDO TEST {side}...")
                print(f"   Precio Entrada: {current_price}")
                print(f"   SL Objetivo: {sl_price:.2f}")
                
                # Ejecutamos la orden usando tu OrderManager
                exito, res = om.ejecutar_estrategia(plan)
                
                if exito:
                    print("\n✨ RESULTADO: ¡EXITOSO!")
                    print("⚠️ IMPORTANTE: Ve a la App de Binance AHORA y verifica:")
                    print("   1. ¿Hay una Posición Abierta?")
                    print("   2. ¿Hay una Orden Pendiente (STOP MARKET)?")
                else:
                    print("\n💀 RESULTADO: FALLIDO. Revisa el error arriba.")

            elif choice == 'C':
                print("\n🧹 Cerrando todo...")
                om.cerrar_posicion(Config.SYMBOL, "MANUAL_TEST")

    except Exception as e:
        print(f"\n💥 CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()