import sys
import os
import time
import uuid

# Ajustar ruta para importar módulos hermanos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import Config
from logs.system_logger import SystemLogger
from execution.order_manager import OrderManager
from execution.comptroller import Comptroller

# --- 1. CREAMOS UN "DOBLE" DE LA API (MOCK) ---
class MockAPIManager:
    """Simula ser Binance para no arriesgar dinero ni requerir conexión real."""
    def __init__(self):
        print("   [MOCK API] 🎭 Iniciando simulador de Exchange...")

    def place_order(self, params):
        """Simula recibir una orden y devolver éxito."""
        tipo = params.get('type')
        lado = params.get('side')
        precio = params.get('price', 'MARKET')
        qty = params.get('quantity')
        
        print(f"   [MOCK API] 📨 Orden Recibida: {tipo} {lado} x {qty} @ {precio}")
        
        # Devolvemos un ID falso como lo haría Binance
        return {'orderId': str(uuid.uuid4())[:8]}

    def cancel_order(self, symbol, orderId):
        print(f"   [MOCK API] 🗑️ Orden Cancelada: {orderId}")
        return True
    
    def get_ticker_price(self, symbol):
        return 100.00 # Precio base simulado

# --- 2. EL GUION DE LA PRUEBA ---
def correr_simulacion():
    print("\n🧪 --- INICIANDO PRUEBA DE ESTRÉS OPERATIVO (SANDBOX) ---")
    
    # A. Inicializamos Departamentos con el Mock
    log = SystemLogger()
    mock_api = MockAPIManager()
    
    # Inyectamos el Mock en lugar de la conexión real
    om = OrderManager(Config, mock_api, log)
    # Pasamos 'None' en financials por ahora
    comp = Comptroller(Config, om, None, log) 

    # B. Creamos un Plan de Tiro Falso (Long en AAVE)
    precio_entrada = 100.00
    plan = {
        'strategy': 'TEST_LAB',
        'side': 'LONG',
        'qty': 1.0,           # 1 AAVE
        'entry_price': precio_entrada,
        'sl_price': 98.00,    # SL al 2%
        'tps': [
            {'price': 105.00, 'qty': 0.5}, # TP1
            {'price': 110.00, 'qty': 0.5}  # TP2
        ]
    }

    print("\n👉 PASO 1: Ejecución de Orden (OrderManager)")
    ok, paquete = om.ejecutar_estrategia(plan)
    
    if not ok:
        print("❌ Fallo en ejecución inicial.")
        return

    print(f"✅ Orden Ejecutada. ID Posición: {paquete['id']}")
    
    print("\n👉 PASO 2: Custodia (Contralor)")
    comp.aceptar_custodia(paquete)
    print(f"   Posiciones bajo custodia: {len(comp.posiciones_activas)}")

    # C. Simulamos Movimiento de Mercado
    # El Contralor tiene reglas:
    # - B/E si gana 1% (Precio > 101.00)
    # - Trailing si gana 2% (Precio > 102.00)
    
    escenarios = [
        (100.50, "Precio sube un poco (Nada pasa)"),
        (101.20, "Precio sube 1.2% (Debería activar Break Even)"),
        (102.50, "Precio sube 2.5% (Debería activar Trailing Stop)"),
        (103.00, "Precio sube a 3.0% (Trailing debería subir SL)"),
        (90.00,  "CRASH repentino (Debería haber cerrado por SL simulado)") 
    ]

    print("\n👉 PASO 3: Simulación de Mercado (Inyección de Precios)")
    
    for precio_simulado, descripcion in escenarios:
        print(f"\n--- 💹 Ticker Simulado: ${precio_simulado} ({descripcion}) ---")
        
        # Llamamos al auditor manualmente
        comp.auditar_posiciones(precio_simulado)
        
        # Verificamos estado interno
        pos = comp.posiciones_activas[paquete['id']]
        print(f"   🔍 Estado Actual -> SL: {pos['sl_price']} | B/E: {pos['be_activado']} | TS: {pos['ts_activado']}")
        
        time.sleep(1) # Pausa dramática para leer

    print("\n✅ PRUEBA FINALIZADA. Revisa 'logs/bitacora_actividad.log' para la auditoría oficial.")

if __name__ == "__main__":
    correr_simulacion()