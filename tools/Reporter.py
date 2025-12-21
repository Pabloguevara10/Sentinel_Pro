# =============================================================================
# ARCHIVO: tools/Reporter.py
# DESCRIPCIÓN: Módulo estandarizado para generación de métricas y CSVs de auditoría.
# USO: Importado por TrendHunter, FlashScalp y SniperForensic.
# =============================================================================

import pandas as pd
import os
from datetime import datetime

class TradingReporter:
    def __init__(self, simulator_name, initial_capital=1000):
        self.name = simulator_name
        self.initial_capital = initial_capital
        self.trades = []
        
    def add_trade(self, trade_dict):
        """
        Agrega una operación cerrada al registro.
        Esperamos un diccionario con claves estandarizadas.
        """
        self.trades.append(trade_dict)
        
    def generate_report(self):
        if not self.trades:
            print(f"⚠️ {self.name}: No se generaron operaciones para reportar.")
            return

        df = pd.DataFrame(self.trades)
        
        # --- CÁLCULO DE MÉTRICAS ---
        total_trades = len(df)
        wins = df[df['PnL_Pct'] > 0]
        losses = df[df['PnL_Pct'] <= 0]
        
        win_rate = (len(wins) / total_trades) * 100
        
        # Simulación de Equity
        equity = [self.initial_capital]
        for pnl in df['PnL_Pct']:
            equity.append(equity[-1] * (1 + pnl))
            
        final_capital = equity[-1]
        total_pnl_pct = ((final_capital - self.initial_capital) / self.initial_capital) * 100
        
        # Drawdown
        equity_curve = pd.Series(equity)
        running_max = equity_curve.cummax()
        drawdown = (equity_curve - running_max) / running_max
        max_dd = drawdown.min() * 100
        
        # Factor de Calidad (Profit Factor simplificado)
        avg_win = wins['PnL_Pct'].mean() if not wins.empty else 0
        avg_loss = abs(losses['PnL_Pct'].mean()) if not losses.empty else 0
        risk_reward = avg_win / avg_loss if avg_loss > 0 else 0

        # --- IMPRESIÓN EN PANTALLA ---
        print("\n" + "="*60)
        print(f"🏁 REPORTE FINAL: {self.name.upper()}")
        print("="*60)
        print(f"📅 Fecha Reporte     : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"💰 Capital Inicial   : ${self.initial_capital:,.2f}")
        print(f"📈 Capital Final     : ${final_capital:,.2f}")
        print(f"📊 PnL Total         : {total_pnl_pct:+.2f}%")
        print("-" * 60)
        print(f"🏆 Operaciones       : {total_trades}")
        print(f"✅ Tasa de Acierto   : {win_rate:.1f}% ({len(wins)} Ganadas)")
        print(f"📉 Máximo Drawdown   : {max_dd:.2f}%")
        print(f"⚖️ Ratio B/R Promedio: {risk_reward:.2f}")
        print("="*60)

        # --- GUARDADO CSV ---
        if not os.path.exists('reports'):
            os.makedirs('reports')
            
        filename = f"reports/{self.name}_AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Columnas prioritarias para el CSV
        cols_order = [
            'Trade_ID', 'Strategy', 'Side', 'Entry_Time', 'Entry_Price', 
            'Exit_Time', 'Exit_Price', 'PnL_Pct', 'Exit_Reason', 
            'Structure_Context', 'Fibo_Target'
        ]
        
        # Reordenar si las columnas existen, sino dejar las que estén
        existing_cols = [c for c in cols_order if c in df.columns]
        rest_cols = [c for c in df.columns if c not in existing_cols]
        df = df[existing_cols + rest_cols]
        
        df.to_csv(filename, index=False)
        print(f"📁 Auditoría guardada en: {filename}")
        print("="*60 + "\n")