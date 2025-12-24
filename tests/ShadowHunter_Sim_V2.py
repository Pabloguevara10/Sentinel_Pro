# =============================================================================
# NOMBRE: ShadowHunter_Sim_V2.py (Cascading Shadows)
# DESCRIPCIÓN: 
#   Estrategia Shadow Hunter Evolucionada.
#   - PERMITE MÚLTIPLES SOMBRAS SIMULTÁNEAS (Cascada).
#   - Filtro de Espaciado (ATR) para no saturar entradas.
#   - Gestión independiente de cada "Sombra".
# =============================================================================

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

# --- CONFIGURACIÓN DE RUTAS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
data_dir = os.path.join(project_root, 'data', 'historical')
reports_dir = os.path.join(project_root, 'reports')

if not os.path.exists(reports_dir): os.makedirs(reports_dir)

class SimConfig:
    SYMBOL = "AAVEUSDT"
    QTY_PRECISION = 1     
    PRICE_PRECISION = 2   
    MIN_QTY = 0.1
    
    FILE_15M = os.path.join(data_dir, "AAVEUSDT_15m.csv")
    
    # --- PARÁMETROS SHADOW HUNTER V2 ---
    BB_PERIOD = 20
    BB_STD_DEV = 2.0
    
    # Gestión de Capital
    BASE_UNIT_USD = 100.0
    
    # Reglas de Cascada (NUEVO)
    MAX_SLOTS = 5           # Máximo 5 operaciones simultáneas por lado
    MIN_SPACING_ATR = 1.0   # Distancia mínima entre entradas (Evitar clusters)
    
    # Reglas de Salida
    CASHFLOW_TARGET_PCT = 0.80 
    SHADOW_TRAILING_PCT = 0.05 
    
    # Seguridad
    MAX_ADD_ONS = 1

# --- HERRAMIENTAS ---
class MockPrecisionLab:
    @staticmethod
    def calcular_bollinger(df, period=20, std_dev=2.0):
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        width = upper - lower
        return upper, sma, lower, width

    @staticmethod
    def calcular_atr(df, period=14):
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        tr1 = high - low
        tr2 = (high - close).abs()
        tr3 = (low - close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

# --- MOTOR SIMULADOR V2 ---
class ShadowHunterSimulatorV2:
    def __init__(self):
        self.trades_history = []
        # Ahora usamos listas para manejar múltiples posiciones
        self.positions = {'LONG': [], 'SHORT': []} 
        self.lab = MockPrecisionLab()
        print(f"🤖 INICIANDO SHADOW HUNTER V2 (CASCADING)")

    def cargar_datos(self):
        print("⏳ Cargando datos históricos...")
        try:
            self.df = pd.read_csv(SimConfig.FILE_15M)
            self.df['datetime'] = pd.to_datetime(self.df['timestamp'], unit='ms')
            
            self.df['bb_upper'], self.df['bb_mid'], self.df['bb_lower'], self.df['bb_width'] = \
                self.lab.calcular_bollinger(self.df, SimConfig.BB_PERIOD, SimConfig.BB_STD_DEV)
            
            if 'atr' not in self.df.columns:
                self.df['atr'] = self.lab.calcular_atr(self.df)
            
            self.df.dropna(inplace=True)
            self.df.reset_index(drop=True, inplace=True)
            print(f"✅ Datos listos: {len(self.df)} velas.")
        except Exception as e:
            print(f"❌ Error cargando datos: {e}")
            sys.exit(1)

    def _redondear_qty(self, qty):
        fmt = "{:." + str(SimConfig.QTY_PRECISION) + "f}"
        return float(fmt.format(qty))

    def _ejecutar_simulacion(self):
        print("🚀 Cazando Sombras en Cascada...")
        
        for i, row in self.df.iterrows():
            # 1. GESTIONAR POSICIONES ABIERTAS
            self._gestionar_posiciones('LONG', row)
            self._gestionar_posiciones('SHORT', row)
            
            # 2. BUSCAR NUEVAS ENTRADAS
            self._buscar_entradas(row)

    def _buscar_entradas(self, row):
        price = row['close']
        upper = row['bb_upper']
        lower = row['bb_lower']
        atr = row['atr']
        
        # --- ENTRY SHORT ---
        if row['high'] >= upper:
            # Lógica de Cascada: ¿Tengo espacio? ¿Estoy lejos de la última?
            if self._puedo_abrir('SHORT', price, atr):
                qty = self._redondear_qty((SimConfig.BASE_UNIT_USD * 2) / price)
                self._abrir_posicion('SHORT', price, qty, row, "BAND_TOUCH_TOP")
            
            # Lógica de Add-on (Revisar cada posición individualmente)
            for pos in self.positions['SHORT']:
                if pos['adds_count'] < SimConfig.MAX_ADD_ONS:
                     if price > pos['entry_price'] * 1.01: # 1% en contra
                        qty = self._redondear_qty(SimConfig.BASE_UNIT_USD / price)
                        self._agregar_margen(pos, price, qty, row)

        # --- ENTRY LONG ---
        if row['low'] <= lower:
            if self._puedo_abrir('LONG', price, atr):
                qty = self._redondear_qty((SimConfig.BASE_UNIT_USD * 2) / price)
                self._abrir_posicion('LONG', price, qty, row, "BAND_TOUCH_BOTTOM")
            
            for pos in self.positions['LONG']:
                if pos['adds_count'] < SimConfig.MAX_ADD_ONS:
                     if price < pos['entry_price'] * 0.99:
                        qty = self._redondear_qty(SimConfig.BASE_UNIT_USD / price)
                        self._agregar_margen(pos, price, qty, row)

    def _puedo_abrir(self, side, price, atr):
        active_positions = self.positions[side]
        
        # 1. Filtro de Cupos
        if len(active_positions) >= SimConfig.MAX_SLOTS:
            return False
            
        # 2. Filtro de Espaciado (Evitar entradas pegadas)
        if len(active_positions) > 0:
            last_entry = active_positions[-1]['entry_price']
            dist = abs(price - last_entry)
            min_dist = atr * SimConfig.MIN_SPACING_ATR
            if dist < min_dist:
                return False
                
        return True

    def _abrir_posicion(self, side, price, qty, row, reason):
        pos = {
            'id': f"{side[0]}_{int(row['timestamp']/1000)}_{len(self.positions[side])}",
            'side': side,
            'entry_time': row['datetime'],
            'entry_price': price,
            'qty_total': qty,
            'qty_cashflow': qty / 2,
            'qty_shadow': qty / 2,
            'adds_count': 0,
            'cashflow_closed': False,
            'max_pnl_pct': 0.0
        }
        self.positions[side].append(pos)

    def _agregar_margen(self, pos, price, qty, row):
        old_val = pos['qty_total'] * pos['entry_price']
        new_val = qty * price
        new_total = pos['qty_total'] + qty
        new_avg = (old_val + new_val) / new_total
        
        pos['entry_price'] = new_avg
        pos['qty_total'] = new_total
        # Recalcular partición (Mantener 50% nocional original en shadow o diluir?)
        # Simplificación: Todo el nuevo margen va a proteger el total.
        # Solo rebalanceamos si cashflow sigue abierto.
        if not pos['cashflow_closed']:
            pos['qty_cashflow'] = new_total / 2
            pos['qty_shadow'] = new_total / 2
        else:
            # Si ya se cerró cashflow, todo es shadow
            pos['qty_shadow'] = new_total
            
        pos['adds_count'] += 1

    def _gestionar_posiciones(self, side, row):
        # Iterar sobre una copia para poder borrar elementos de la lista original
        for pos in self.positions[side][:]:
            self._procesar_posicion(pos, row)
            
            # Limpieza si se cerró completa
            if pos['qty_total'] <= 0.0001:
                self.positions[side].remove(pos)

    def _procesar_posicion(self, pos, row):
        price = row['close']
        bb_width_usd = row['bb_width'] * row['bb_mid']
        
        # Objetivo Cashflow Dinámico
        if pos['side'] == 'LONG':
            target_cf = pos['entry_price'] + (bb_width_usd * SimConfig.CASHFLOW_TARGET_PCT)
            pnl_pct = (price - pos['entry_price']) / pos['entry_price']
        else:
            target_cf = pos['entry_price'] - (bb_width_usd * SimConfig.CASHFLOW_TARGET_PCT)
            pnl_pct = (pos['entry_price'] - price) / pos['entry_price']

        # 1. Cierre Cashflow
        if not pos['cashflow_closed']:
            hit_target = (pos['side'] == 'LONG' and row['high'] >= target_cf) or \
                         (pos['side'] == 'SHORT' and row['low'] <= target_cf)
            
            if hit_target:
                exit_px = target_cf
                self._registrar_trade(pos, row, exit_px, pos['qty_cashflow'], "CASHFLOW_TAKE")
                pos['qty_total'] -= pos['qty_cashflow']
                pos['qty_cashflow'] = 0
                pos['cashflow_closed'] = True
                return # Salir por esta vela para actualizar estado en sig ciclo

        # 2. Gestión Sombra (Solo si PnL es positivo)
        if pnl_pct > pos['max_pnl_pct']: 
            pos['max_pnl_pct'] = pnl_pct
        
        # Trailing Logic
        if pos['max_pnl_pct'] > 0.01: # Solo activar trailing si ganamos > 1%
            trail_dist = SimConfig.SHADOW_TRAILING_PCT
            trigger = pos['max_pnl_pct'] - trail_dist
            
            should_close = pnl_pct < trigger
            
            if should_close:
                # Asegurar que cerramos en ganancia o BE minimo
                if pnl_pct > 0:
                    self._registrar_trade(pos, row, price, pos['qty_total'], "SHADOW_TRAIL")
                    pos['qty_total'] = 0

    def _registrar_trade(self, pos, row, price, qty, reason):
        entry = pos['entry_price']
        side = pos['side']
        pnl = (price - entry) * qty if side == 'LONG' else (entry - price) * qty
        
        self.trades_history.append({
            'ID': pos['id'],
            'Side': side,
            'Entry_Date': pos['entry_time'],
            'Exit_Date': row['datetime'],
            'Reason': reason,
            'PnL_USD': round(pnl, 2),
            'Duration_Days': (row['datetime'] - pos['entry_time']).total_seconds()/86400
        })

    def generar_reporte(self):
        df = pd.DataFrame(self.trades_history)
        if df.empty:
            print("⚠️ Sin operaciones.")
            return
            
        total = df['PnL_USD'].sum()
        print(f"\n📊 SHADOW HUNTER V2 RESULTS")
        print(f"Total PnL: ${total:.2f}")
        print(f"Trades (Events): {len(df)}")
        
        path = os.path.join(reports_dir, f"ShadowHunter_V2_AUDIT_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        df.to_csv(path, index=False)
        print(f"✅ Reporte: {path}")

if __name__ == "__main__":
    sim = ShadowHunterSimulatorV2()
    sim.cargar_datos()
    sim._ejecutar_simulacion()
    sim.generar_reporte()