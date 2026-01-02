# =============================================================================
# UBICACIÓN: interfaces/dashboard.py
# DESCRIPCIÓN: CENTRO DE COMANDO TÁCTICO V18.3 (COMPATIBLE RICH 14.0+)
# =============================================================================

import os
import time
from datetime import datetime
from config.config import Config
from data.calculator import Calculator

# LIBRERÍA RICH (Manejo robusto de importaciones)
RICH_AVAILABLE = False
try:
    # Intentamos la importación moderna (Rich 10+)
    from rich.console import Console, Group
    from rich.table import Table
    from rich import box
    from rich.panel import Panel
    from rich.text import Text
    from rich.align import Align
    from rich.layout import Layout
    RICH_AVAILABLE = True
except ImportError as e:
    # Diagnóstico para que no falle silenciosamente
    print(f"⚠️ [DASHBOARD] Error cargando Rich: {e}")
    print("ℹ️ Intentando fallback...")
    try:
        # Intento Legacy (Rich < 10)
        from rich.console import Console
        from rich.group import Group
        from rich.table import Table
        from rich import box
        from rich.panel import Panel
        from rich.text import Text
        from rich.align import Align
        RICH_AVAILABLE = True
    except ImportError:
        print("❌ [DASHBOARD] Fallo crítico cargando librería visual. Usando modo texto.")
        RICH_AVAILABLE = False

class Dashboard:
    def __init__(self):
        self.start_time = time.time()
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None

    def render(self, data):
        """
        Renderiza la interfaz completa.
        ESTRATEGIA ANTI-FLICKER: Calcular todo ANTES de limpiar la pantalla.
        """
        # Fallback
        if not RICH_AVAILABLE:
            self._render_legacy(data)
            return

        # =====================================================================
        # 1. FASE DE CÁLCULO (MANTENIENDO PANTALLA ANTERIOR)
        # =====================================================================
        
        try:
            # A. Datos Generales
            price = data.get('price', 0.0)
            fin = data.get('financials', {})
            conn = data.get('connections', {})
            positions = data.get('positions', [])
            
            uptime = str(datetime.now() - datetime.fromtimestamp(self.start_time)).split('.')[0]
            balance = fin.get('balance', 0.0)
            
            # B. Matriz Matemática (Lectura de disco pesada)
            matriz_data = Calculator.generar_matriz_dashboard(Config.SYMBOL, Config.DIR_DATA)

            # =====================================================================
            # 2. FASE DE CONSTRUCCIÓN VISUAL (EN MEMORIA)
            # =====================================================================

            # HEADER
            header_text = Text(f"🤖 {Config.BOT_NAME} | ⏱️ {uptime} | 💰 BAL: ${balance:,.2f} | 📡 API: {'🟢' if conn.get('binance') else '🔴'}", style="bold white on blue")
            panel_header = Panel(Align.center(header_text), box=box.SQUARE, style="blue")

            # TABLA MATRIZ
            table_matrix = Table(title=f"MATRIZ DE MERCADO ({Config.SYMBOL} @ ${price:,.2f})", box=box.SQUARE, show_lines=True, header_style="bold cyan")
            
            table_matrix.add_column("TF", justify="center", width=6, style="bold")
            table_matrix.add_column("TEND", justify="center", width=6)
            table_matrix.add_column("RSI (14)", justify="center", width=10)
            table_matrix.add_column("ADX (14)", justify="center", width=10)
            table_matrix.add_column("MACD H.", justify="center", width=10)
            table_matrix.add_column("VOL", justify="center", width=8)
            table_matrix.add_column("BB WIDTH", justify="center", width=10)
            table_matrix.add_column("STOCH K", justify="center", width=10)

            tfs_order = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d']
            
            for tf in tfs_order:
                ind = matriz_data.get(tf, {})
                if not ind:
                    table_matrix.add_row(tf, "-", "-", "-", "-", "-", "-", "-")
                    continue
                
                # Lógica de Colores
                rsi_val = ind['rsi']
                c_rsi = "green" if rsi_val < 30 else ("red" if rsi_val > 70 else "yellow")
                
                adx_val = ind['adx']
                c_adx = "green" if adx_val > 25 else "yellow"
                
                macd_val = ind['macd_hist']
                c_macd = "green" if macd_val > 0 else "red"
                
                stoch_val = ind['stoch_k']
                c_stoch = "green" if stoch_val < 20 else ("red" if stoch_val > 80 else "yellow")
                
                trend_sc = ind['trend']
                trend_icon = "🟢 ▲" if trend_sc == 1 else ("🔴 ▼" if trend_sc == -1 else "🟡 ─")
                
                vol_txt = ind['vol_change']
                c_vol = "green" if vol_txt == "UP" else ("red" if vol_txt == "DN" else "yellow")

                # Formateo Monospace Rígido
                row = [
                    tf,
                    trend_icon,
                    f"[{c_rsi}]{rsi_val:05.1f}[/]",
                    f"[{c_adx}]{adx_val:05.1f}[/]",
                    f"[{c_macd}]{macd_val:+.2f}[/]",
                    f"[{c_vol}]{vol_txt}[/]",
                    f"{ind['bb_width']:05.2f}%",
                    f"[{c_stoch}]{stoch_val:05.1f}[/]"
                ]
                table_matrix.add_row(*row)

            # TABLA POSICIONES
            table_pos = Table(title="🛡️ POSICIONES ACTIVAS", box=box.SQUARE, show_lines=True, header_style="bold magenta")
            table_pos.add_column("ID", width=8)
            table_pos.add_column("SIDE", width=6)
            table_pos.add_column("MODO", width=14)
            table_pos.add_column("ENTRY", justify="right", width=10)
            table_pos.add_column("QTY", justify="right", width=8)
            table_pos.add_column("PNL %", justify="right", width=10)
            table_pos.add_column("ESTADO", width=15)
            table_pos.add_column("SL / TP", width=20)

            if not positions:
                table_pos.add_row("-", "-", "SIN ACTIVIDAD", "-", "-", "-", "💤 ESPERANDO", "-")
            else:
                for p in positions:
                    entry = float(p.get('entry_price', 0))
                    qty = float(p.get('qty', 0))
                    sl = float(p.get('sl_price', 0))
                    side = p.get('side', 'UNK')
                    pnl_pct = p.get('pnl_pct', 0) * 100
                    
                    is_blindada = False
                    if side == 'LONG' and sl > entry: is_blindada = True
                    if side == 'SHORT' and sl < entry: is_blindada = True
                    
                    status_txt = "🔒 BLINDADA" if is_blindada else "🛡️ PROTEGIDA"
                    status_style = "bold green" if is_blindada else "yellow"
                    pnl_style = "green" if pnl_pct > 0 else "red"
                    side_style = "blue" if side == 'LONG' else "magenta"
                    oid = p.get('id', 'unk')[:8]

                    table_pos.add_row(
                        oid,
                        f"[{side_style}]{side}[/]",
                        p.get('mode', 'MANUAL')[:14],
                        f"${entry:,.2f}",
                        f"{qty:.2f}",
                        f"[{pnl_style}]{pnl_pct:+.2f}%[/]",
                        f"[{status_style}]{status_txt}[/]",
                        f"SL: {sl:.2f}"
                    )

            # BITÁCORA FOOTER
            footer = Panel("📟 SISTEMA OPERATIVO Y VIGILANTE. ESCANEO CONTINUO...", style="dim white", box=box.SIMPLE)

            # Agrupamos todo en un objeto renderizable
            vista_completa = Group(
                panel_header,
                table_matrix,
                table_pos,
                footer
            )

            # =====================================================================
            # 3. FASE DE IMPRESIÓN (ATÓMICA)
            # =====================================================================
            
            # Borrado instantáneo justo antes de imprimir
            os.system('cls' if os.name == 'nt' else 'clear')
            self.console.print(vista_completa)
            
        except Exception as e:
            # Si falla el renderizado, mostramos error en consola normal pero no detenemos el bot
            print(f"⚠️ Error Renderizado Dashboard: {e}")

    def _render_legacy(self, data):
        print(f"--- DASHBOARD LEGACY ---")
        print(f"PRICE: {data.get('price')}")
        print("Instala 'rich' o revisa los logs de importación.")