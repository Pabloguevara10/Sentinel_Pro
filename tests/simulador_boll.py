import pandas as pd
import numpy as np
import os

def get_lagged_indicators(df, index, indicators, lags=5):
    """Obtiene los valores T0 a T-(lags-1) para los indicadores dados."""
    data = {}
    for ind in indicators:
        for lag in range(lags):
            suffix = f"T-{lag}" if lag > 0 else "T0"
            col_name = f"{ind.upper()}_{suffix}"
            lookback_idx = index - lag
            if lookback_idx >= 0:
                data[col_name] = df.at[lookback_idx, ind]
            else:
                data[col_name] = np.nan
    return data

def audit_bollinger(file_path, fvg_path=None, lookahead=20):
    if not os.path.exists(file_path):
        print(f"No encontrado: {file_path}")
        return None
    
    df = pd.read_csv(file_path)
    
    # Cargar FVG
    df_fvg = None
    if fvg_path and os.path.exists(fvg_path):
        df_fvg = pd.read_csv(fvg_path)
        if not np.issubdtype(df_fvg['timestamp'].dtype, np.datetime64):
            df_fvg['timestamp'] = pd.to_datetime(df_fvg['timestamp'], unit='ms')
            df_fvg = df_fvg.sort_values('timestamp')

    # Convertir timestamps
    if not np.issubdtype(df['timestamp'].dtype, np.datetime64):
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    results = []
    indicators = ['rsi', 'volume', 'macd', 'adx', 'atr']
    timeframe_name = os.path.basename(file_path).replace('.csv', '').split('_')[-1] # e.g., '15m'

    # Empezar loop con margen para lags
    for i in range(5, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i-1]
        
        if pd.isna(row['bb_upper']):
            continue

        signals = []
        
        # 1. Upper Touch (Short)
        if row['high'] >= row['bb_upper']:
            signals.append({'type': 'SHORT', 'side': 'SHORT', 'price': row['bb_upper']})
        
        # 2. Lower Touch (Long)
        if row['low'] <= row['bb_lower']:
            signals.append({'type': 'LONG', 'side': 'LONG', 'price': row['bb_lower']})
            
        # 3. Mid Cross
        if row['low'] <= row['bb_mid'] <= row['high']:
            if prev_row['close'] > prev_row['bb_mid']:
                signals.append({'type': 'LONG_MID', 'side': 'LONG', 'price': row['bb_mid']})
            else:
                signals.append({'type': 'SHORT_MID', 'side': 'SHORT', 'price': row['bb_mid']})

        if not signals:
            continue
            
        # Datos históricos de indicadores
        lagged_data = get_lagged_indicators(df, i, indicators, lags=5)
        
        # FVG relevantes (anteriores a la vela actual)
        relevant_fvgs = pd.DataFrame()
        if df_fvg is not None:
            relevant_fvgs = df_fvg[df_fvg['timestamp'] < row['timestamp']]

        # Futuro para PnL
        future_window = df.iloc[i+1 : i+1+lookahead]
        
        for sig in signals:
            ref_price = sig['price']
            
            # Check FVG
            is_in_fvg = False
            if not relevant_fvgs.empty:
                matches = relevant_fvgs[(relevant_fvgs['bottom'] <= ref_price) & (relevant_fvgs['top'] >= ref_price)]
                if not matches.empty:
                    is_in_fvg = True

            # Performance
            max_adv = 0.0
            max_dd = 0.0
            if len(future_window) > 0:
                highs = future_window['high']
                lows = future_window['low']
                if sig['side'] == 'LONG':
                    max_adv = (highs.max() - ref_price) / ref_price * 100
                    max_dd = (ref_price - lows.min()) / ref_price * 100
                else:
                    max_adv = (ref_price - lows.min()) / ref_price * 100
                    max_dd = (highs.max() - ref_price) / ref_price * 100

            record = {
                'Timestamp': row['timestamp'],
                'Timeframe': timeframe_name,
                'Signal_Type': sig['type'],
                'Signal_Price': round(ref_price, 4),
                'In_FVG': is_in_fvg,
                'Max_Advance_Pct': round(max_adv, 2),
                'Max_Drawdown_Pct': round(max_dd, 2)
            }
            record.update(lagged_data)
            results.append(record)

    return pd.DataFrame(results)

# Ejecución principal
timeframes = ['5m', '15m', '30m', '1h', '1d']
symbol = 'AAVEUSDT'
base_path = 'data/historical' # Ajusta tu ruta si es necesario

for tf in timeframes:
    file = f"{base_path}/{symbol}_{tf}.csv"
    fvg = f"{base_path}/mapas_fvg/mapa_fvg_{tf}.csv"
    
    print(f"Procesando {tf}...")
    df_audit = audit_bollinger(file, fvg)
    
    if df_audit is not None and not df_audit.empty:
        out_name = f"AUDITORIA_BB_{symbol}_{tf}.csv"
        df_audit.to_csv(out_name, index=False)
        print(f"Guardado: {out_name}")