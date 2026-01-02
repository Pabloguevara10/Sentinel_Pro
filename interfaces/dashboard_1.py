# =============================================================================
# UBICACIÓN: interfaces/dashboard.py
# DESCRIPCIÓN: DASHBOARD V16.5 (VISUAL FIX COMPLETO)
# =============================================================================

import os
import time
from datetime import datetime

class Dashboard:
    def __init__(self):
        self.last_render = 0
        self.start_time = time.time()

    def render(self, data):
        # Limpieza
        os.system('cls' if os.name == 'nt' else 'clear')
        
        price = data.get('price', 0.0)
        fin = data.get('financials', {})
        mkt = data.get('market', {})
        conn = data.get('connections', {})
        positions = data.get('positions', [])
        
        uptime = str(datetime.now() - datetime.fromtimestamp(self.start_time)).split('.')[0]
        
        binance_txt = "🟢 ONLINE" if conn.get('binance') else "🔴 OFFLINE"
        tele_txt = "🟢 ONLINE" if conn.get('telegram') else "⚪ OFF"

        print("="*78)
        print(f"   🤖 SENTINEL PRO (V16.5) | ⏱️ {uptime} | 🧠 BRAIN ACTIVE")
        print("="*78)
        print(f" 📡 Binance: {binance_txt:<15} | ✈️ Telegram: {tele_txt}")
        print("-" * 78)
        
        pnl = fin.get('daily_pnl', 0.0)
        sym_pnl = "+" if pnl >= 0 else ""
        print(f" 💰 Balance: ${fin.get('balance', 0):,.2f}      | 📉 PnL Sesión: {sym_pnl}${pnl:.2f}")
        print("-" * 78)
        
        rsi = mkt.get('rsi', 0)
        rsi_tag = ""
        if rsi > 70: rsi_tag = "⚠️ OVERBOUGHT"
        elif rsi < 30: rsi_tag = "💎 OVERSOLD"
        
        print(f" 📊 {mkt.get('symbol','---'):<10} ${price:,.2f} | 📈 RSI: {rsi:.1f} {rsi_tag}")
        print("="*78)
        print(f" 🛡️ POSICIONES ACTIVAS ({len(positions)})")
        
        if not positions:
            print("\n    [ESCANEO EN PROGRESO... 🦅]\n")
        else:
            # Cabecera corregida con MODO y anchos ajustados
            print(f" {'ID':<8} | {'MODO':<12} | {'SIDE':<5} | {'ENTRY':<9} | {'ROI':<7} | {'ESTADO'}")
            print("-" * 78)
            
            for pos in positions:
                # 1. Recuperación de ID
                oid = pos.get('id', 'N/A')
                if not oid or oid == 'N/A': 
                    # Si no hay ID, usamos parte del símbolo como fallback
                    oid = pos.get('symbol', 'UNK')[-4:]
                
                # 2. Estrategia (MODO)
                strat = pos.get('strategy', 'MANUAL')
                if not strat: strat = 'UNKNOWN'
                strat = strat[:12] # Recortar
                
                # 3. Datos Financieros
                entry = pos.get('entry_price', 0)
                side = pos.get('side', '?')
                roi = 0.0
                if entry > 0 and price > 0:
                    if side == 'LONG': roi = (price - entry)/entry * 100
                    else: roi = (entry - price)/entry * 100
                
                # 4. Estado
                status = "🛡️ PROTECTED"
                if pos.get('status') == 'RECOVERED': status = "♻️ RECOVERED"
                
                print(f" {oid:<8} | {strat:<12} | {side:<5} | ${entry:<9.2f} | {roi:+.2f}% | {status}")

        print("="*78)
        print(" [CTRL+C] Salir | [panic] Cerrar Todo (Telegram)")