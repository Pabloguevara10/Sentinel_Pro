# =============================================================================
# UBICACIÓN: logs/system_logger.py
# DESCRIPCIÓN: Logger Híbrido (Persistencia CSV + Alias V15)
# =============================================================================

import logging
import csv
import time
from datetime import datetime
import os
from config.config import Config

class SystemLogger:
    """
    DEPARTAMENTO DE AUDITORÍA: Responsable de los libros contables.
    VERSION: 8.3-HYBRID (Soporta Main V15 y Persistencia CSV)
    """
    def __init__(self):
        # Configurar logger base
        self.logger = logging.getLogger('Sentinel_Activity')
        self.logger.setLevel(logging.INFO)
        
        # Evitar duplicados de handlers
        if not self.logger.handlers:
            # Crear directorio si no existe
            if not os.path.exists(Config.DIR_LOGS):
                os.makedirs(Config.DIR_LOGS)

            fh = logging.FileHandler(Config.FILE_LOG_ACTIVITY, encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            
            # Consola
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

        # 2. Libro de Órdenes (CRÍTICO: Mantenemos estructura V8.3)
        if not os.path.exists(Config.FILE_LOG_ORDERS):
            with open(Config.FILE_LOG_ORDERS, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['ID_POSICION', 'TIMESTAMP', 'ESTRATEGIA', 'SIDE', 'PRECIO_ENTRADA', 'QTY', 'SL_PRICE', 'SL_ORDER_ID', 'TP_CONFIG', 'ESTADO'])

    # --- MÉTODOS DE REGISTRO (LEGACY & V15) ---

    def registrar_actividad(self, modulo, mensaje):
        """Registro narrativo."""
        self.logger.info(f"[{modulo}] {mensaje}")

    def registrar_error(self, modulo, error_obj, critico=False):
        """Registro de errores en CSV y Log."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        nivel = "CRITICO" if critico else "ADVERTENCIA"
        msg = str(error_obj)
        
        # CSV Errores
        try:
            with open(Config.FILE_LOG_ERRORS, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, modulo, nivel, msg, ""])
        except: pass
        
        self.logger.error(f"[{modulo}] ❌ {nivel}: {msg}")

    def registrar_orden(self, paquete_orden):
        """Persistencia de Órdenes en CSV (Vital para auditoría)."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with open(Config.FILE_LOG_ORDERS, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    paquete_orden.get('id'),
                    timestamp,
                    paquete_orden.get('strategy'),
                    paquete_orden.get('side'),
                    paquete_orden.get('entry_price'),
                    paquete_orden.get('qty'),
                    paquete_orden.get('sl_price'),
                    paquete_orden.get('sl_order_id', 'N/A'),
                    str(paquete_orden.get('tps_config', [])), 
                    'ABIERTA'
                ])
            self.registrar_actividad("AUDITORIA", f"📝 Orden {paquete_orden.get('id')[:8]} asentada en libros.")
        except Exception as e:
            self.logger.error(f"Error escribiendo orden CSV: {e}")

    # --- ALIAS DE COMPATIBILIDAD V15 (Necesarios para el nuevo Main) ---
    def log_info(self, mensaje):
        self.registrar_actividad("SYSTEM", mensaje)

    def log_warn(self, mensaje):
        self.logger.warning(f"[SYSTEM] ⚠️ {mensaje}")

    def log_error(self, mensaje):
        self.registrar_error("SYSTEM", mensaje)