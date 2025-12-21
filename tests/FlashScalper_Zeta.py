# =============================================================================
# NOMBRE: FlashScalper_Zeta_V2.py (Reversal + BandWidth Filter)
# UBICACIÓN: tests/FlashScalper_Zeta_V2.py
# =============================================================================
import pandas as pd
import numpy as np
import os
import sys

# --- CONFIGURACIÓN ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
tools_path = os.path.join(project_root, 'tools')
sys.path.append(tools_path)

try:
    from Reporter import TradingReporter
except ImportError:
    pass

class Config:
    FILE_1M = "../data/historical/AAVEUSDT_1m.csv"
    
    # FILTROS
    MIN_BB_WIDTH = 0.02    # 2% Mínimo de ancho de banda
    VOL_MULT = 2.5         # Volumen > 2.5x promedio
    
    # GESTIÓN FRACCIONADA
    TP1_QTY = 0.60
    TP2_QTY = 0.20
    RUNNER_QTY = 0.20
    
    # Riesgo Base (Stop Loss fijo inicial por si acaso explota en contra)
    SL_FIXED_PCT = 0.015   # 1.5% (Amplio, confiamos en la reversión)

class FlashScalperV2:
    def __init__(self):
        try:
            self.reporter = TradingReporter("FlashScalper_V2_Reversal", initial_capital=1000)
        except:
            self.reporter = None
            
        self.positions = []
        self.df = self._load_data()

    def _load_data(self):
        path = os.path.join(os.path.dirname(__file__), Config.FILE_1M)
        if not os.path.exists(path): return pd.DataFrame()
        df = pd.read_csv(path)
        df.columns = [c.lower().strip() for c in df.columns]
        
        # Timestamp
        if 'timestamp' in df.columns:
            if df['timestamp'].iloc[0] > 10000000000:
                 df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            else:
                 df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
        # Indicadores
        df['vol_ma'] = df['volume'].rolling(20).mean()
        
        # Bollinger (20, 2)
        sma = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std()
        df['bb_upper'] = sma + (std * 2)
        df['bb_lower'] = sma - (std * 2)
        df['bb_mid'] = sma
        
        # Ancho de Banda: (Upper - Lower) / Mid
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
        
        return df.dropna()

    def run(self):
        if self.df.empty: return
        print(f"⚡ FLASH V2: Procesando {len(self.df)} velas (Filtro > 2%)...")
        
        for i in range(50, len(self.df)):
            row = self.df.iloc[i]
            
            # GESTIÓN
            if self.positions:
                self._manage(self.positions[0], row)
                if self.positions[0]['status'] == 'CLOSED':
                    if self.reporter: self.reporter.add_trade(self.positions[0])
                    self.positions.clear()
                continue
            
            # ENTRADA (REVERSAL + QUALITY)
            # 1. Filtro de Calidad (Ancho)
            if row['bb_width'] < Config.MIN_BB_WIDTH: continue
            
            # 2. Señal (Volumen + Ruptura)
            vol_cond = row['volume'] > (row['vol_ma'] * Config.VOL_MULT)
            
            signal = None
            if vol_cond:
                # Si rompe arriba -> SHORT (Apostamos a que regresa)
                if row['close'] > row['bb_upper']:
                    signal = 'GO_SHORT'
                # Si rompe abajo -> LONG
                elif row['close'] < row['bb_lower']:
                    signal = 'GO_LONG'
            
            if signal:
                entry = row['close']
                side = 'LONG' if signal == 'GO_LONG' else 'SHORT'
                sl = entry * (1 - Config.SL_FIXED_PCT) if side == 'LONG' else entry * (1 + Config.SL_FIXED_PCT)
                
                self.positions.append({
                    'Trade_ID': f"FL_{row.name.strftime('%H%M')}",
                    'Strategy': 'Flash_Reversal',
                    'Side': side,
                    'Entry_Time': row.name, 'Entry_Price': entry,
                    'Exit_Time': None, 'Exit_Price': None, 'PnL_Pct': 0.0,
                    'Exit_Reason': None,
                    'SL': sl, 'Peak_Price': entry,
                    'status': 'OPEN',
                    'Rem_Qty': 1.0, 'TP1_Hit': False, 'TP2_Hit': False
                })
        
        if self.reporter: self.reporter.generate_report()

    def _manage(self, trade, row):
        curr = row['close']
        entry = trade['Entry_Price']
        side = trade['Side']
        
        # Bandas Dinámicas Actuales (Target Móvil)
        mid = row['bb_mid']
        upper = row['bb_upper']
        lower = row['bb_lower']
        band_range = upper - lower
        
        # Definir Niveles Dinámicos
        if side == 'LONG':
            tp1_price = mid
            tp2_price = lower + (band_range * 0.75) # 75% del camino hacia arriba
            
            # SL Check
            if curr <= trade['SL']:
                self._close(trade, curr, row.name, 'SL_HIT')
                return
                
            # TP1 (Media)
            if not trade['TP1_Hit'] and curr >= tp1_price:
                trade['TP1_Hit'] = True
                trade['Rem_Qty'] -= Config.TP1_QTY
                trade['SL'] = entry # Break Even
                
            # TP2 (75%)
            if not trade['TP2_Hit'] and curr >= tp2_price:
                trade['TP2_Hit'] = True
                trade['Rem_Qty'] -= Config.TP2_QTY
                trade['SL'] = tp1_price # Asegurar ganancia en TP1
                
            # Runner Trailing (Solo si pasamos TP2)
            if trade['TP2_Hit']:
                trade['Peak_Price'] = max(trade['Peak_Price'], curr)
                dyn_sl = trade['Peak_Price'] * 0.995 # 0.5% trailing
                if dyn_sl > trade['SL']: trade['SL'] = dyn_sl
                
        else: # SHORT
            tp1_price = mid
            tp2_price = upper - (band_range * 0.75) # 75% del camino hacia abajo
            
            if curr >= trade['SL']:
                self._close(trade, curr, row.name, 'SL_HIT')
                return
                
            if not trade['TP1_Hit'] and curr <= tp1_price:
                trade['TP1_Hit'] = True
                trade['Rem_Qty'] -= Config.TP1_QTY
                trade['SL'] = entry
                
            if not trade['TP2_Hit'] and curr <= tp2_price:
                trade['TP2_Hit'] = True
                trade['Rem_Qty'] -= Config.TP2_QTY
                trade['SL'] = tp1_price
                
            if trade['TP2_Hit']:
                trade['Peak_Price'] = min(trade['Peak_Price'], curr)
                dyn_sl = trade['Peak_Price'] * 1.005
                if dyn_sl < trade['SL']: trade['SL'] = dyn_sl

    def _close(self, trade, price, time, reason):
        # Calculo PnL Ponderado aproximado
        entry = trade['Entry_Price']
        side = trade['Side']
        raw_pnl = (price - entry)/entry if side == 'LONG' else (entry - price)/entry
        
        # Reconstruir PnL por partes
        # (Esto es una aproximación para el reporte, asumiendo TP hit perfecto)
        # En producción se calcula exacto con el balance.
        total_pnl = 0.0
        locked_qty = 0.0
        
        # TP1 Gain (aprox a la media, digamos entry a mid es ~0.5 width?)
        # Usaremos el precio de cierre final para simplificar la auditoría si fue SL
        # Si TP1 fue hit, asumimos ganancia positiva en esa parte.
        
        # Simplificación Robusta: PnL = (Precio Salida - Entrada) * Cantidad Restante + PnL ya cobrado
        # Pero como no guardamos el PnL cobrado en la variable, usaremos PnL final * 100% 
        # (El reporte será conservador: si el precio se devuelve, asume que todo se devolvió, 
        #  aunque en realidad cobramos. Para auditoría, mejor ver el Exit Reason).
        
        trade['Exit_Price'] = price
        trade['Exit_Time'] = time
        trade['Exit_Reason'] = reason
        trade['status'] = 'CLOSED'
        trade['PnL_Pct'] = raw_pnl # Guardamos el PnL de la última parte

if __name__ == "__main__":
    FlashScalperV2().run()