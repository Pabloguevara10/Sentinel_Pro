import os
import time
from datetime import datetime

class Dashboard:
    """
    INTERFAZ VISUAL V8.4 (Restaurada):
    Recreación del dashboard clásico con secciones de Finanzas, Mercado y Control.
    """
    def __init__(self):
        self.last_render = 0
        self.start_time = time.time()

    def add_log(self, msg):
        # Muestra logs en tiempo real sin borrar pantalla si es necesario
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {msg}")

    def render(self, data):
        """
        Renderiza el reporte completo en consola.
        Esperamos 'data' con llaves: price, financials, market, connections, positions
        """
        # 1. Limpieza de Pantalla (Cross-Platform)
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # 2. Extracción de Datos Segura (Valores por defecto si faltan)
        price = data.get('price', 0.0)
        
        # Finanzas
        fin = data.get('financials', {})
        balance = fin.get('balance', 0.0)
        pnl = fin.get('daily_pnl', 0.0)
        
        # Mercado
        mkt = data.get('market', {})
        rsi = mkt.get('rsi', 0.0)
        vol = mkt.get('volumen', 0.0)
        symbol = mkt.get('symbol', 'AAVEUSDT')
        
        # Conexiones
        conn = data.get('connections', {})
        binance_ok = "🟢 ONLINE" if conn.get('binance') else "🔴 OFFLINE"
        tele_ok = "🟢 ONLINE" if conn.get('telegram') else "⚪ OFF"
        
        # Posiciones
        positions = data.get('positions', []) # Esperamos una lista de dicts
        
        # Tiempo de actividad
        uptime = str(datetime.now() - datetime.fromtimestamp(self.start_time)).split('.')[0]

        # --- 3. DIBUJADO DEL REPORTE (Estilo Clásico) ---
        print("="*60)
        print(f"   🤖 SENTINEL AI PRO (V8.4) | ⏱️ Uptime: {uptime}")
        print("="*60)
        
        # SECCIÓN 1: ESTADO DEL SISTEMA
        print(f" 📡 API Binance:  {binance_ok:<15} | ✈️ Telegram: {tele_ok}")
        print("-" * 60)
        
        # SECCIÓN 2: FINANZAS (Simulado si no hay wallet real)
        pnl_symbol = "+" if pnl >= 0 else ""
        print(f" 💰 Balance Total: ${balance:,.2f}       | 📉 PnL Diario: {pnl_symbol}${pnl:.2f}")
        print("-" * 60)
        
        # SECCIÓN 3: MERCADO (Data en tiempo real)
        print(f" 📊 Ticker: {symbol:<10} | 💲 Precio: ${price:,.2f}")
        
        # Lógica visual para RSI
        rsi_status = ""
        if rsi > 70: rsi_status = "(SOBRECOMPRA ⚠️)"
        elif rsi < 30: rsi_status = "(SOBREVENTA 💎)"
        
        print(f" 📈 RSI (5m): {rsi:.2f} {rsi_status:<15} | 📊 Volumen: {vol:.2f}")
        print("="*60)
        
        # SECCIÓN 4: POSICIONES ACTIVAS
        print(f" 🛡️ GESTIÓN DE POSICIONES ({len(positions)} Activas)")
        if not positions:
            print("    [ESPERANDO OPORTUNIDAD... 🦅]")
        else:
            print(f" {'ID':<8} | {'SIDE':<5} | {'ENTRY':<10} | {'ROI':<8} | {'ESTADO'}")
            print("-" * 60)
            for pos in positions:
                # Calcular ROI visual
                entry = pos.get('entry_price', 0)
                side = pos.get('side', 'N/A')
                roi = 0.0
                if entry > 0:
                    if side == 'LONG': roi = (price - entry) / entry * 100
                    else: roi = (entry - price) / entry * 100
                
                roi_str = f"{roi:+.2f}%"
                print(f" {pos.get('id', '')[:8]:<8} | {side:<5} | ${entry:<9.2f} | {roi_str:<8} | 🛡️ CUSTODIA")

        print("="*60)
        print(" [CTRL+C] para Detener | [S] Logs Sistema")