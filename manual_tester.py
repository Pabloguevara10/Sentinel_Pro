import time
import os
import sys

# Aseguramos que Python encuentre las carpetas del proyecto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from connections.api_manager import APIManager
from execution.order_manager import OrderManager
<<<<<<< HEAD
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
=======
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
>>>>>>> 4c4d97b (commit 24/12)
    
    logger = DummyLogger()
    
    try:
<<<<<<< HEAD
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
=======
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
>>>>>>> 4c4d97b (commit 24/12)
            print(" [X] Salir")
            
            choice = input("\n👉 Comando: ").upper().strip()
            
            if choice == 'X': break
            
            if choice == 'L' or choice == 'S':
                side = 'LONG' if choice == 'L' else 'SHORT'
                
<<<<<<< HEAD
                # Obtenemos precio actual
=======
                # A. Obtener precio real
>>>>>>> 4c4d97b (commit 24/12)
                current_price = api.get_ticker_price(Config.SYMBOL)
                if current_price == 0:
                    print("❌ Error: No se pudo obtener precio de mercado.")
                    continue

<<<<<<< HEAD
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
=======
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
>>>>>>> 4c4d97b (commit 24/12)

    except Exception as e:
        print(f"\n💥 CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()