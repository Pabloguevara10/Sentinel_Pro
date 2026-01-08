# =============================================================================
# UBICACIÓN: logic/evaluator.py
# DESCRIPCIÓN: BLACKBOX EVALUATOR V1.0 (DATA COLLECTOR)
# =============================================================================

import os
import csv
import pandas as pd
from datetime import datetime

class Evaluator:
    """
    BLACKBOX V1.0:
    Registra el contexto técnico (Indicadores, Tendencia) al momento de la entrada
    y posteriormente registra el resultado (PnL) al cierre.
    Objetivo: Crear un Dataset para análisis estadístico y futuro Machine Learning.
    """
    def __init__(self, logger=None):
        self.log = logger
        self.filepath = "logs/blackbox_dataset.csv"
        self._inicializar_csv()

    def _inicializar_csv(self):
        """Crea el archivo con cabeceras si no existe."""
        if not os.path.exists(self.filepath):
            headers = [
                'TRADE_ID', 'TIMESTAMP', 'STRATEGY', 'SIDE', 'ENTRY_PRICE',
                # --- FACTORES TÉCNICOS (FEATURES) ---
                'RSI_15M', 'ADX_15M', 'MACD_HIST_15M', 'ATR_15M',
                'RSI_1H', 'ADX_1H', 'TREND_1H_EMA',
                'PERF_50_CANDLES_PCT', # Rendimiento de las últimas 50 velas
                'VOLATILITY_PCT',      # Volatilidad relativa
                # --- RESULTADO (TARGETS) ---
                'CLOSE_PRICE', 'FINAL_PNL_PCT', 'RESULT', 'EXIT_REASON'
            ]
            try:
                with open(self.filepath, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
            except Exception as e:
                if self.log: self.log.registrar_error("EVAL", f"Fallo init CSV: {e}")

    def registrar_entrada(self, plan, data_map):
        """
        Toma una 'FOTO' del mercado justo antes de entrar.
        """
        try:
            # Extraemos datos
            df_15 = data_map.get('15m')
            df_1h = data_map.get('1h')
            
            if df_15 is None or df_15.empty: return
            if df_1h is None or df_1h.empty: return

            # Última vela cerrada (Contexto inmediato)
            row15 = df_15.iloc[-1]
            row1h = df_1h.iloc[-1]
            
            # Cálculo de Tendencia (50 velas atrás)
            # Si hay suficientes datos, comparamos precio actual vs hace 50 velas
            perf_50 = 0.0
            if len(df_15) > 50:
                past_close = df_15.iloc[-50]['close']
                curr_close = row15['close']
                perf_50 = (curr_close - past_close) / past_close

            # Volatilidad relativa (ATR / Precio)
            volatility = 0.0
            if row15['close'] > 0:
                volatility = row15.get('atr', 0) / row15['close']

            # Construcción de la fila
            new_row = [
                plan['id'],                 # TRADE_ID
                datetime.now().isoformat(), # TIMESTAMP
                plan['strategy'],           # STRATEGY
                plan['side'],               # SIDE
                plan['entry_price'],        # ENTRY_PRICE
                # Indicadores 15m
                round(row15.get('rsi', 0), 2),
                round(row15.get('adx', 0), 2),
                round(row15.get('macd_hist', 0), 4),
                round(row15.get('atr', 0), 4),
                # Indicadores 1H
                round(row1h.get('rsi', 0), 2),
                round(row1h.get('adx', 0), 2),
                "UP" if row1h.get('ema_fast', 0) > row1h.get('ema_slow', 0) else "DOWN",
                # Contexto
                round(perf_50 * 100, 2),    # % Rendimiento previo
                round(volatility * 100, 2), # % Volatilidad
                # Placeholders de salida
                0, 0, "PENDING", "OPEN"
            ]
            
            with open(self.filepath, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(new_row)
                
            if self.log: self.log.registrar_actividad("EVAL", f"📸 Snapshot guardado ID: {plan['id']}")

        except Exception as e:
            if self.log: self.log.registrar_error("EVAL", f"Error registrando entrada: {e}")

    def registrar_salida(self, trade_id, close_price, pnl_pct, reason):
        """
        Busca la línea del trade_id y completa los datos de salida.
        (Nota: Esta versión usa Pandas para editar el CSV fácilmente, 
         si el archivo es gigante a futuro se puede optimizar).
        """
        try:
            if not os.path.exists(self.filepath): return

            # Leemos todo el CSV
            df = pd.read_csv(self.filepath)
            
            # Buscamos el índice
            idx = df.index[df['TRADE_ID'] == trade_id].tolist()
            
            if not idx: return # No encontrado (quizás operación manual o muy vieja)
            
            i = idx[0]
            
            # Actualizamos datos
            df.at[i, 'CLOSE_PRICE'] = close_price
            df.at[i, 'FINAL_PNL_PCT'] = round(pnl_pct * 100, 2)
            df.at[i, 'RESULT'] = "WIN" if pnl_final_pct > 0 else "LOSS"
            df.at[i, 'EXIT_REASON'] = reason
            
            # Guardamos
            df.to_csv(self.filepath, index=False)
            
            if self.log: self.log.registrar_actividad("EVAL", f"📝 Resultado actualizado ID: {trade_id} ({df.at[i, 'RESULT']})")

        except Exception as e:
            # Fallo silencioso para no interrumpir operativa crítica
            pass