import logging
import csv
import time
from datetime import datetime
import os
from config.config import Config

class SystemLogger:
    """
    DEPARTAMENTO DE AUDITORÍA: Responsable de los 4 libros contables.
    VERSION: 8.3 (Incluye SL_ORDER_ID en persistencia)
    """
    def __init__(self):
        # Configurar logger base para actividad general
        self.logger = logging.getLogger('Sentinel_Activity')
        self.logger.setLevel(logging.INFO)
        
        # Evitar duplicados de handlers si se reinicia
        if not self.logger.handlers:
            fh = logging.FileHandler(Config.FILE_LOG_ACTIVITY, encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            
            # También mostrar en consola
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)
            
        self._inicializar_csvs()

    def _inicializar_csvs(self):
        """Crea los encabezados de los libros si están vacíos."""
        # 1. Libro de Errores
        if not os.path.exists(Config.FILE_LOG_ERRORS):
            with open(Config.FILE_LOG_ERRORS, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['TIMESTAMP', 'MODULO', 'TIPO_ERROR', 'MENSAJE', 'TRACEBACK'])

        # 2. Libro de Órdenes y Posiciones (CRÍTICO - ACTUALIZADO)
        if not os.path.exists(Config.FILE_LOG_ORDERS):
            with open(Config.FILE_LOG_ORDERS, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # FIX: Agregado SL_ORDER_ID al encabezado
                writer.writerow(['ID_POSICION', 'TIMESTAMP', 'ESTRATEGIA', 'SIDE', 'PRECIO_ENTRADA', 'QTY', 'SL_PRICE', 'SL_ORDER_ID', 'TP_CONFIG', 'ESTADO'])

    # --- METODOS DE REGISTRO ---

    def registrar_actividad(self, modulo, mensaje):
        """Libro 2: Bitácora de Actividad (Narrativa)."""
        self.logger.info(f"[{modulo}] {mensaje}")

    def registrar_error(self, modulo, error_obj, critico=False):
        """Libro 1: Bitácora de Errores."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        nivel = "CRITICO" if critico else "ADVERTENCIA"
        msg = str(error_obj)
        
        # Escribir en CSV
        with open(Config.FILE_LOG_ERRORS, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, modulo, nivel, msg, ""])
        
        # También notificar en el log narrativo
        self.logger.error(f"[{modulo}] ❌ {nivel}: {msg}")

    def registrar_orden(self, paquete_orden):
        """Libro 3: Bitácora de Órdenes (Contabilidad)."""
        # Se llama cuando el Gestor de Órdenes confirma la ejecución en Binance
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(Config.FILE_LOG_ORDERS, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # FIX: Guardamos el SL_ORDER_ID real
            writer.writerow([
                paquete_orden.get('id'),
                timestamp,
                paquete_orden.get('strategy'),
                paquete_orden.get('side'),
                paquete_orden.get('entry_price'),
                paquete_orden.get('qty'),
                paquete_orden.get('sl_price'),
                paquete_orden.get('sl_order_id', 'N/A'), # Nuevo campo
                str(paquete_orden.get('tps_config', [])), 
                'ABIERTA'
            ])
        self.registrar_actividad("AUDITORIA", f"📝 Orden {paquete_orden.get('id')[:8]} asentada en libros.")