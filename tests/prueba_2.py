# =============================================================================
# UBICACIÓN: tests/Simulador_Full_Context.py
# DESCRIPCIÓN: Simulador Jerárquico (4H -> 1H -> 15m -> 1m)
# OBJETIVO: Operar solo en Zonas de Interés Mayores con Confirmación
# =============================================================================

import pandas as pd
import numpy as np
import os
import warnings

warnings.filterwarnings('ignore')

class ConfigSim:
    SYMBOL = "AAVEUSDT"
    CAPITAL_INICIAL = 1000.0
    LEVERAGE = 5 
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_FILE = os.path.join(BASE_DIR, "data", "historical", f"{SYMBOL}_1m.csv")
    
    # --- GESTIÓN DE RIESGO ---
    PCT_CAPITAL_PER_TRADE = 0.05
    
    # --- FILTROS DE ESTRUCTURA (MACRO) ---
    # Tolerancia para considerar que el precio está en una "Zona 4H"
    TOLERANCIA_ZONA_4H = 0.015 # 1.5% de distancia del soporte/resistencia
    
    # --- FILTROS DE ENTRADA (MICRO) ---
    RSI_LONG = 30
    RSI_SHORT = 70
    
    # --- SALIDA (High R/R) ---
    SL_PCT = 0.020        # 2% Riesgo
    TP1_PCT = 0.035       # 3.5% Target Inicial
    TRAILING_ACT = 0.035  # Activar trailing en TP1
    TRAILING_DIST = 0.010 # Distancia 1%

# =============================================================================
# 1. ESCÁNER DE ZONAS (4H)
# =============================================================================
class ZoneScanner:
    def __init__(self, df_4h):
        self.df = df_4h.copy()
        
    def precompute(self):
        # Detectar Pivotes Fractal en 4H (Soportes y Resistencias Relevantes)
        # Usamos una ventana de 3 velas a cada lado para ser estrictos
        window = 3
        self.df['max_roll'] = self.df['high'].rolling(window=window*2+1, center=True).max()
        self.df['min_roll'] = self.df['low'].rolling(window=window*2+1, center=True).min()
        
        self.df['is_resistance'] = (self.df['high'] == self.df['max_roll'])
        self.df['is_support'] = (self.df['low'] == self.df['min_roll'])
        
        # Limpiar
        self.df.drop(columns=['max_roll', 'min_roll'], inplace=True)
        print(f"   [4H Scanner] Zonas Detectadas: {self.df['is_support'].sum()} Soportes, {self.df['is_resistance'].sum()} Resistencias")

    def check_zone_proximity(self, current_time, current_price):
        # Buscar zonas PASADAS (No mirar al futuro)
        past_df = self.df.loc[:current_time].iloc[:-1] # Excluir vela actual para no repintar
        if past_df.empty: return 'NEUTRAL'
        
        # Obtener los últimos 5 soportes y resistencias
        supports = past_df[past_df['is_support']]['low'].tail(5).values
        resistances = past_df[past_df['is_resistance']]['high'].tail(5).values
        
        # Verificar cercanía (Long en Soporte, Short en Resistencia)
        for s in supports:
            dist = abs(current_price - s) / current_price
            if dist < ConfigSim.TOLERANCIA_ZONA_4H:
                return 'ZONE_SUPPORT'
                
        for r in resistances:
            dist = abs(current_price - r) / current_price
            if dist < ConfigSim.TOLERANCIA_ZONA_4H:
                return 'ZONE_RESISTANCE'
                
        return 'NEUTRAL'

# =============================================================================
# 2. MOTOR DE INDICADORES
# =============================================================================
def add_indicators(df):
    cols = [c.lower() for c in df.columns]
    # RSI
    if 'rsi' not in cols:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 0.0001)
        df['rsi'] = 100 - (100 / (1 + rs))
    # EMA 200 (Tendencia 1H)
    if 'ema_200' not in cols:
        df['ema_200'] = df['close'].ewm(span=200).mean()
    # MACD
    if 'macd_hist' not in cols:
        k = df['close'].ewm(span=12).mean(); d = df['close'].ewm(span=26).mean()
        df['macd_hist'] = (k-d) - (k-d).ewm(span=9).mean()
        
    return df.dropna()

# =============================================================================
# 3. SIMULADOR FULL CONTEXT
# =============================================================================
class SimuladorContexto:
    def __init__(self):
        print(f"🚀 Iniciando Simulador FULL CONTEXTO: {ConfigSim.SYMBOL}")
        print("   Estructura: 4H (Zonas) -> 1H (Tendencia) -> 15m (Gatillo)")
        
        # Carga Data
        try:
            self.df_1m = pd.read_csv(ConfigSim.DATA_FILE)
            self._prep_data()
        except: print("❌ Error Data"); exit()
        
        # Generar Timeframes Jerárquicos
        print("⏳ Generando 4H, 1H, 15m...")
        agg = {'open':'first', 'high':'max', 'low':'min', 'close':'last'}
        
        self.df_15m = self.df_1m.resample('15min', closed='right', label='right').agg(agg).dropna()
        self.df_1h = self.df_1m.resample('1h', closed='right', label='right').agg(agg).dropna()
        self.df_4h = self.df_1m.resample('4h', closed='right', label='right').agg(agg).dropna()
        
        # Indicadores Específicos
        self.df_15m = add_indicators(self.df_15m)
        self.df_1h = add_indicators(self.df_1h) # Necesitamos EMA 200 y MACD aquí
        
        # Scanner 4H (Solo necesitamos Estructura de precio, no indicadores complejos)
        self.scanner_4h = ZoneScanner(self.df_4h)
        self.scanner_4h.precompute()
        
        self.capital = ConfigSim.CAPITAL_INICIAL; self.posicion = None; self.historial = []

    def _prep_data(self):
        df = self.df_1m
        df.columns = [c.lower().strip() for c in df.columns]
        if 'close' not in df.columns: df.columns = ['timestamp','open','high','low','close','volume'][:6]
        ts_col = 'timestamp' if 'timestamp' in df.columns else 'time'
        if df[ts_col].iloc[0] > 1000000000000: df[ts_col] = pd.to_datetime(df[ts_col], unit='ms')
        else: df[ts_col] = pd.to_datetime(df[ts_col])
        df.set_index(ts_col, inplace=True)
        for c in ['open','high','low','close']: df[c] = pd.to_numeric(df[c], errors='coerce')
        self.df_1m = df.dropna()

    def ejecutar(self):
        print("\n▶️ RUNNING (Escaneando Zonas 4H + Tendencia 1H)...")
        
        for ts, row in self.df_1m.iterrows():
            if self.posicion: self._check_exit(ts, row)
            
            # Revisar entrada solo en cierres de 15m
            if ts.minute % 15 == 0 and not self.posicion:
                self._check_entry(ts)
        self._reporte()

    def _check_entry(self, ts):
        # Sincronizar Contextos
        if ts not in self.df_15m.index: return
        
        # 1. CONTEXTO 4H (¿Estamos en zona?)
        # Buscamos la vela 4H cerrada más reciente
        ts_4h = self.df_4h.index.asof(ts)
        zone_status = self.scanner_4h.check_zone_proximity(ts_4h, self.df_15m.loc[ts]['close'])
        
        # Si no estamos en zona clave, ABORTAR (Filtro de Calidad Máxima)
        # Nota: Puedes comentar esto para probar "sin zonas", pero es lo que pediste.
        if zone_status == 'NEUTRAL': return 

        # 2. CONTEXTO 1H (Tendencia)
        ts_1h = self.df_1h.index.asof(ts)
        if pd.isna(ts_1h) or ts_1h not in self.df_1h.index: return
        row_1h = self.df_1h.loc[ts_1h]
        trend_bullish = row_1h['close'] > row_1h['ema_200']
        
        # 3. GATILLO 15m
        row_15m = self.df_15m.loc[ts]
        rsi = row_15m['rsi']
        
        signal = None
        
        # LÓGICA DE ALINEACIÓN
        # LONG: Zona Soporte 4H + Tendencia 1H Alcista + RSI 15m Sobreventa
        if zone_status == 'ZONE_SUPPORT' and trend_bullish and rsi < ConfigSim.RSI_LONG:
            signal = 'LONG'
            
        # SHORT: Zona Resistencia 4H + Tendencia 1H Bajista + RSI 15m Sobrecompra
        elif zone_status == 'ZONE_RESISTANCE' and not trend_bullish and rsi > ConfigSim.RSI_SHORT:
            signal = 'SHORT'
            
        if signal:
            self._open(signal, ts, row_15m['close'])

    def _open(self, side, time, price):
        cfg = ConfigSim
        if side == 'LONG':
            sl = price * (1 - cfg.SL_PCT)
            tp1 = price * (1 + cfg.TP1_PCT)
        else:
            sl = price * (1 + cfg.SL_PCT)
            tp1 = price * (1 - cfg.TP1_PCT)
            
        self.posicion = {
            'side': side, 'entry_price': price, 'entry_time': time,
            'sl': sl, 'tp1': tp1, 'tp1_hit': False,
            'max_p': price, 'min_p': price,
            'size': self.capital * cfg.PCT_CAPITAL_PER_TRADE * cfg.LEVERAGE
        }

    def _check_exit(self, ts, row):
        pos = self.posicion
        h = row['high']; l = row['low']; cfg = ConfigSim
        
        # Update Peaks for Trailing
        if pos['side'] == 'LONG': 
            pos['max_p'] = max(pos['max_p'], h)
            pnl_max = (pos['max_p'] - pos['entry_price'])/pos['entry_price']
        else: 
            pos['min_p'] = min(pos['min_p'], l)
            pnl_max = (pos['entry_price'] - pos['min_p'])/pos['entry_price']
            
        # Trailing Logic (Solo post TP1)
        if pnl_max >= cfg.TRAILING_ACT:
            if pos['side'] == 'LONG': pos['sl'] = max(pos['sl'], pos['max_p']*(1-cfg.TRAILING_DIST))
            else: pos['sl'] = min(pos['sl'], pos['min_p']*(1+cfg.TRAILING_DIST))
            
        # Execution
        sl_hit = (pos['side']=='LONG' and l<=pos['sl']) or (pos['side']=='SHORT' and h>=pos['sl'])
        if sl_hit:
            pnl = (pos['sl']-pos['entry_price'])/pos['entry_price'] if pos['side']=='LONG' else (pos['entry_price']-pos['sl'])/pos['entry_price']
            usd = pos['size']*pnl
            self.capital += usd
            self.historial.append({'exit': ts, 'pnl': usd, 'reason': 'SL/Trail'})
            self.posicion = None; return
            
        # TP1 Hit (Breakeven)
        if not pos['tp1_hit']:
            hit = (pos['side']=='LONG' and h>=pos['tp1']) or (pos['side']=='SHORT' and l<=pos['tp1'])
            if hit:
                # Sell 50%
                usd = pos['size'] * 0.5 * cfg.TP1_PCT
                self.capital += usd
                pos['size'] *= 0.5 # Reduce size
                pos['tp1_hit'] = True
                # Move SL to BE
                if pos['side']=='LONG': pos['sl'] = max(pos['sl'], pos['entry_price']*1.001)
                else: pos['sl'] = min(pos['sl'], pos['entry_price']*0.999)
                self.historial.append({'exit': ts, 'pnl': usd, 'reason': 'TP1'})

    def _reporte(self):
        if not self.historial: print("\n⚠️ 0 Trades (Estructura muy estricta)."); return
        df = pd.DataFrame(self.historial)
        print(f"\n💰 FINAL: ${self.capital:,.2f}")
        df.to_csv(os.path.join(os.path.dirname(__file__), "Resultado_Full_Context.csv"), index=False)

if __name__ == "__main__":
    SimuladorContexto().ejecutar()