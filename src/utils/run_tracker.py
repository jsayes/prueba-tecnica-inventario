"""Registro de ejecuciones, watermarks, rechazos y archivos procesados.

Esta pieza está implementada: el ETL debe usarla para que toda ejecución quede
trazada en el schema etl.
"""
from __future__ import annotations

import json
from typing import Any

from src.utils.db import connection
from src.utils.logger import get_logger

logger = get_logger(__name__)


def iniciar_ejecucion(flujo: str, parametros: dict[str, Any] | None = None) -> int:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO etl.ejecucion (flujo, parametros, estado)
                    VALUES (%s, %s, 'EN_CURSO') RETURNING id_ejecucion""",
            (flujo, json.dumps(parametros or {})),
        )
        return cur.fetchone()[0]


def cerrar_ejecucion(id_ejecucion: int, estado: str, metricas: dict, error: str | None = None) -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE etl.ejecucion
                  SET estado = %s, filas_leidas = %s, filas_cargadas = %s,
                      filas_rechazadas = %s, mensaje_error = %s, finalizado_en = now()
                WHERE id_ejecucion = %s""",
            (
                estado,
                metricas.get("leidas", 0),
                metricas.get("cargadas", 0),
                metricas.get("rechazadas", 0),
                error,
                id_ejecucion,
            ),
        )


def registrar_rechazos(id_ejecucion: int, flujo: str, rechazos: list[tuple[dict, str]]) -> None:
    if not rechazos:
        return
    with connection() as conn, conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO etl.rechazo (id_ejecucion, flujo, regla, payload)
                    VALUES (%s, %s, %s, %s)""",
            [(id_ejecucion, flujo, regla, json.dumps(r, default=str)) for r, regla in rechazos],
        )


def leer_watermark(flujo: str) -> str | None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT valor FROM etl.watermark WHERE flujo = %s", (flujo,))
        row = cur.fetchone()
        return row[0] if row else None


def escribir_watermark(flujo: str, valor: str) -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO etl.watermark (flujo, valor)
                    VALUES (%s, %s)
               ON CONFLICT (flujo)
                 DO UPDATE SET valor = EXCLUDED.valor, actualizado_en = now()""",
            (flujo, valor),
        )


def archivo_ya_procesado(flujo: str, nombre: str, hash_contenido: str) -> bool:
    """True si el archivo ya se cargó con el mismo contenido."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT hash_contenido FROM etl.archivo_procesado
                WHERE flujo = %s AND nombre_archivo = %s""",
            (flujo, nombre),
        )
        row = cur.fetchone()
    if row is None:
        return False
    if row[0] != hash_contenido:
        logger.warning("El archivo %s cambió de contenido desde la última carga", nombre)
        return False
    return True


def marcar_archivo_procesado(flujo: str, nombre: str, hash_contenido: str, filas: int) -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO etl.archivo_procesado (flujo, nombre_archivo, hash_contenido, filas)
                    VALUES (%s, %s, %s, %s)
               ON CONFLICT (flujo, nombre_archivo)
                 DO UPDATE SET hash_contenido = EXCLUDED.hash_contenido,
                               filas = EXCLUDED.filas,
                               procesado_en = now()""",
            (flujo, nombre, hash_contenido, filas),
        )
