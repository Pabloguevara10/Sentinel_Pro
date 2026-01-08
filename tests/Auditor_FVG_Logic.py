# =============================================================================
# UBICACIÓN: tests/Auditor_FVG_Logic.py
# ESTADO: CORREGIDO (Ruta mapas_fvg)
# DESCRIPCIÓN: Auditoría Sniper Institucional (Solo operar en FVG 1D)
# =============================================================================

import pandas as pd
import numpy as np
import os
import warnings

warnings.filterwarnings('ignore')

class ConfigSim:
    SYMBOL = "AAVEUSDT"
    CAPITAL_INICIAL = 1000.0
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_FILE = os.path.join(BASE_DIR, "data", "historical", f"{SYMBOL}_1m.csv")
    
    # --- RUTA CORREGIDA ---
    FVG_FILE = os.path.join(BASE_DIR, "data", "historical", "mapas_fvg", "mapa_fvg_1d.csv")
    
    # ESTRATEGIA "SNIPER INSTITUCIONAL"
    # Entramos si: Precio dentro de FVG 1D + RSI en zona extrema (15m)
    SL_PCT = 0.02   # 2% Riesgo
    TP_PCT = 0.04   # 4% Beneficio (Ratio 1:2)
    
    # Filtros RSI
    RSI_OVERSOLD = 35 # Comprar en Soporte (FVG Bullish)
    RSI_OVERBOUGHT = 65 # Vender en Resistencia (FVG Bearish)

# =============================================================================
# 1. GESTOR DE FVG (MAPA INSTITUCIONAL)
# =============================================================================
class FVGManager:
    def __init__(self):
        self.fvgs = []
        self._load_fvgs()
        
    def _load_fvgs(self):
        if not os.path.exists(ConfigSim.FVG_FILE):
            print(f"❌ ERROR CRÍTICO: No se encuentra {ConfigSim.FVG_FILE}")
            return
        
        try:
            df = pd.read_csv(ConfigSim.FVG_FILE)
            # Asegurar tipos numéricos
            df['top'] = pd.to_numeric(df['top'])
            df['bottom'] = pd.to_numeric(df['bottom'])
            
            # Detectar formato de fecha (ms o segundos)
            if df['timestamp'].iloc[0] > 1000000000000:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            else:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            self.fvgs = df.to_dict('records')
            print(f"✅ Mapa FVG Cargado: {len(self.fvgs)} zonas institucionales detectadas.")
        except Exception as e:
            print(f"❌ Error leyendo CSV FVG: {e}")

    def get_active_zone(self, current_time, current_price):
        """
        Retorna 'BULLISH' si estamos en zona de compra, 'BEARISH' si venta.
        """
        for zone in self.fvgs:
            # El FVG debe existir antes de este momento
            if zone['timestamp'] > current_time: continue
            
            # Verificar si el precio está DENTRO de la zona
            if zone['bottom'] <= current_price <= zone['top']:
                return zone['type']
                
        return None

# =============================================================================
# 2. MOTOR DE SIMULACIÓN
# =============================================================================
class AuditorFVG:
    def __init__(self):
        print(f"🕵️ Iniciando Auditoría FVG: {ConfigSim.SYMBOL}")
        print(f"   Estrategia: Operar Rebotes en FVG 1D (Ratio 1:2)")
        self.fvg_manager = FVGManager()
        self._load_market_data()
        
    def _load_market_data(self):
        print("⏳ Cargando Market Data 1m...")
        try:
            df = pd.read_csv(ConfigSim.DATA_FILE)
            
            # Limpieza estándar
            df.columns = [c.lower().strip() for c in df.columns]
            if 'close' not in df.columns: df.columns = ['timestamp','open','high','low','close','volume'][:6]
            
            # Fix Timestamp
            ts_col = 'timestamp' if 'timestamp' in df.columns else 'time'
            if df[ts_col].iloc[0] > 1000000000000: df[ts_col] = pd.to_datetime(df[ts_col], unit='ms')
            else: df[ts_col] = pd.to_datetime(df[ts_col])
            df.set_index(ts_col, inplace=True)
            
            self.df_1m = df.dropna()
            
            # Resample 15m para tomar decisiones
            self.df_15m = self.df_1m.resample('15min', closed='right', label='right').agg(
                {'open':'first', 'high':'max', 'low':'min', 'close':'last'}).dropna()
                
            # Calcular RSI
            delta = self.df_15m['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, 0.0001)
            self.df_15m['rsi'] = 100 - (100 / (1 + rs))
            
            print(f"✅ Data Sincronizada: {len(self.df_15m)} velas de decisión.")
        except Exception as e:
            print(f"❌ Error cargando market data: {e}"); exit()

    def ejecutar(self):
        print("🔬 Escaneando Oportunidades...")
        trades = []
        capital = ConfigSim.CAPITAL_INICIAL
        
        # Recorremos vela a vela de 15m
        for ts, row in self.df_15m.iterrows():
            
            # 1. Filtro Institucional: ¿Precio dentro de FVG?
            zone_type = self.fvg_manager.get_active_zone(ts, row['close'])
            
            if not zone_type: continue # No operar en tierra de nadie
            
            # 2. Gatillo Técnico: RSI Extremo
            signal = None
            if zone_type == 'BULLISH' and row['rsi'] < ConfigSim.RSI_OVERSOLD:
                signal = 'LONG' # Comprar en Soporte FVG
            elif zone_type == 'BEARISH' and row['rsi'] > ConfigSim.RSI_OVERBOUGHT:
                signal = 'SHORT' # Vender en Resistencia FVG
                
            if signal:
                # 3. Simular Futuro (Ver si toca TP o SL)
                pnl = self._simular_futuro(ts, row['close'], signal)
                trades.append({
                    'timestamp': ts,
                    'signal': signal,
                    'zone': zone_type,
                    'price': row['close'],
                    'pnl': pnl
                })
                capital += pnl
        
        self._reportar(trades, capital)

    def _simular_futuro(self, entry_time, entry_price, side):
        # Buscamos en la data de 1 minuto siguiente (hasta 48 horas máx)
        # Ratio 1:2 -> SL 2%, TP 4%
        
        future = self.df_1m.loc[entry_time:].iloc[1:2880] # 2880 mins = 48 horas
        if future.empty: return 0
        
        tp_price = entry_price * (1 + ConfigSim.TP_PCT) if side == 'LONG' else entry_price * (1 - ConfigSim.TP_PCT)
        sl_price = entry_price * (1 - ConfigSim.SL_PCT) if side == 'LONG' else entry_price * (1 + ConfigSim.SL_PCT)
        
        risk_amount = ConfigSim.CAPITAL_INICIAL * 0.05 # Arriesgamos 5% del capital base por trade
        
        for _, row in future.iterrows():
            if side == 'LONG':
                if row['low'] <= sl_price: return -risk_amount # Perdimos 1R
                if row['high'] >= tp_price: return risk_amount * 2 # Ganamos 2R
            else:
                if row['high'] >= sl_price: return -risk_amount
                if row['low'] <= tp_price: return risk_amount * 2
                
        return 0 # Neutro (Se acabó el tiempo)

    def _reportar(self, trades, final_cap):
        if not trades: 
            print("\n⚠️ 0 Operaciones. El precio no entró en zonas FVG o el RSI no confirmó.")
            return
        
        df = pd.DataFrame(trades)
        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] < 0]
        
        print("\n" + "="*50)
        print(f"📊 REPORTE FVG SNIPER (1D ZONES)")
        print(f"💰 Capital Final: ${final_cap:,.2f}")
        print(f"📈 ROI: ${(final_cap - ConfigSim.CAPITAL_INICIAL):,.2f}")
        print(f"🎯 Win Rate: {len(wins)/len(df)*100:.1f}%")
        print(f"🎲 Total Trades: {len(df)}")
        print(f"✅ Ganadoras: {len(wins)} | ❌ Perdedoras: {len(losses)}")
        print("="*50)
        
        out_file = os.path.join(os.path.dirname(__file__), "Resultado_FVG.csv")
        df.to_csv(out_file, index=False)
        print(f"📄 Detalles guardados en: {out_file}")

if __name__ == "__main__":
    AuditorFVG().ejecutar()