"""Flujos de inventario.

`inventario_historico` está IMPLEMENTADO como referencia. Los flujos intradía
y el cierre diario son tu entregable.
"""
from __future__ import annotations

from datetime import date

from src.config.settings import PROJECT_ROOT, load_config, source_config
from src.extractors.csv_extractor import build_extractor
from src.loaders.fact_loaders import FullOnceLoader, SnapshotCompletoLoader, SnapshotLoader
from src.pipelines.pipeline import Pipeline
from src.pipelines.ventas import _al_terminar, _pipeline_vacio
from src.quality.rules import REGLAS_INVENTARIO, Validador
from src.transformers.base import Chain
from src.transformers.cleaners import sk_fecha
from src.transformers.facts import DimensionResolver, InventarioTransformer
from src.transformers.generic import Deduplicate
from src.utils.db import connection, file_hash
from src.utils.logger import get_logger
from src.utils.run_tracker import archivo_ya_procesado

logger = get_logger(__name__)

COLUMNAS_INVENTARIO_DIARIO = [
    "sk_fecha", "sk_tienda", "sk_articulo", "unidades_disponibles",
    "unidades_transito", "unidades_comprometidas", "costo_promedio",
    "valor_inventario", "hora_snapshot", "fecha_actualizacion",
]


def inventario_historico(periodo: str) -> Pipeline:
    """Carga única de un mes de cierres diarios. periodo: 'AAAAMM'. IMPLEMENTADO."""
    nombre = "fct_inventario_historico"
    cfg = source_config(nombre)
    ruta = PROJECT_ROOT / cfg["path_pattern"].format(periodo=periodo)

    if archivo_ya_procesado(nombre, ruta.name, file_hash(ruta)):
        logger.info("%s ya fue procesado; nada que hacer", ruta.name)
        return _pipeline_vacio(nombre, {"periodo": periodo})

    quality = load_config()["quality"]
    pipeline = Pipeline(
        nombre=nombre,
        extractor=build_extractor(cfg["extractor"], path=ruta),
        transformer=Chain(
            InventarioTransformer(DimensionResolver().cargar()),
            Deduplicate(["sk_fecha", "sk_tienda", "sk_articulo"]),
        ),
        loader=FullOnceLoader(
            cfg["target"],
            ["sk_fecha", "sk_tienda", "sk_articulo"],
            COLUMNAS_INVENTARIO_DIARIO,
        ),
        validador=Validador(REGLAS_INVENTARIO, quality.get("max_reject_ratio"))
        if REGLAS_INVENTARIO
        else None,
        parametros={"periodo": periodo},
    )

    _al_terminar(pipeline, nombre, ruta)
    return pipeline

COLUMNAS_INVENTARIO_INTRADIA = [
    "sk_fecha", "hora_snapshot", "sk_tienda", "sk_articulo", "unidades_disponibles",
    "unidades_transito", "unidades_comprometidas", "costo_promedio", "fecha_actualizacion",
]  # sin valor_inventario ni fecha_snapshot: no existen en core.fct_inventario_intradia

def inventario_intradia(fecha: str, hora: str) -> Pipeline:
    """Carga de un snapshot de 30 minutos. hora: 'HHMM'. TODO — a implementar.

    Reutiliza InventarioTransformer y el patrón de `inventario_historico`; lo
    que cambia es el destino (core.fct_inventario_intradia), el loader
    (UpsertLoader) y la validación de completitud del snapshot.
    """
    nombre = "fct_inventario_intradia"
    cfg = source_config(nombre)
    ruta = PROJECT_ROOT / cfg["path_pattern"].format(
        fecha_archivo=fecha.replace("-", ""), hora=hora
    )
    quality = load_config()["quality"]

    interno = SnapshotLoader(
        cfg["target"], cfg["natural_key"], COLUMNAS_INVENTARIO_INTRADIA,
        scope_columns=["sk_fecha", "hora_snapshot"],
    )
    pipeline = Pipeline(
        nombre=nombre,
        extractor=build_extractor(cfg["extractor"], path=ruta),
        transformer=Chain(
            InventarioTransformer(DimensionResolver().cargar()),
            # llave natural (no sk): los códigos huérfanos no colapsan en una sola fila
            Deduplicate(["codigo_tienda", "codigo_articulo"]),
        ),
        loader=SnapshotCompletoLoader(
            interno,
            min_ratio=quality.get("min_completitud_snapshot", 0.95),
            fallback_esperadas=quality.get("filas_esperadas_snapshot", 1080),
        ),
        validador=Validador(REGLAS_INVENTARIO, quality.get("max_reject_ratio")),
        parametros={"fecha": fecha, "hora": hora},
    )
    _al_terminar(pipeline, nombre, ruta)
    return pipeline


def _asegurar_particion(cur, anio: int) -> None:
    """Crea la partición anual de fct_inventario_diario si no existe."""
    anio = int(anio)
    cur.execute(
        f"""CREATE TABLE IF NOT EXISTS core.fct_inventario_diario_{anio}
            PARTITION OF core.fct_inventario_diario
            FOR VALUES FROM ({anio}0101) TO ({anio + 1}0101)"""  # noqa: S608
    )


SQL_CIERRE = """
WITH ultimo AS (
    SELECT max(hora_snapshot) AS h
      FROM core.fct_inventario_intradia
     WHERE sk_fecha = %(sk)s
)
INSERT INTO core.fct_inventario_diario
    (sk_fecha, sk_tienda, sk_articulo, unidades_disponibles, unidades_transito,
     unidades_comprometidas, costo_promedio, valor_inventario, hora_snapshot,
     fecha_actualizacion)
SELECT i.sk_fecha, i.sk_tienda, i.sk_articulo, i.unidades_disponibles,
       i.unidades_transito, i.unidades_comprometidas, i.costo_promedio,
       i.unidades_disponibles * i.costo_promedio, i.hora_snapshot,
       i.fecha_actualizacion
  FROM core.fct_inventario_intradia i
  JOIN ultimo u ON i.hora_snapshot = u.h
 WHERE i.sk_fecha = %(sk)s
ON CONFLICT (sk_fecha, sk_tienda, sk_articulo) DO UPDATE SET
    unidades_disponibles   = EXCLUDED.unidades_disponibles,
    unidades_transito      = EXCLUDED.unidades_transito,
    unidades_comprometidas = EXCLUDED.unidades_comprometidas,
    costo_promedio         = EXCLUDED.costo_promedio,
    valor_inventario       = EXCLUDED.valor_inventario,
    hora_snapshot          = EXCLUDED.hora_snapshot,
    fecha_actualizacion    = EXCLUDED.fecha_actualizacion,
    fecha_carga            = now()
"""


def cerrar_inventario_dia(fecha: str) -> int:
    """Deriva el cierre diario del último snapshot válido del día. Idempotente.

    Solo se cargan snapshots completos (SnapshotCompletoLoader), así que el
    max(hora_snapshot) del día ya es el último snapshot válido. Reejecutar deja
    el mismo estado (ON CONFLICT DO UPDATE). Crea la partición anual si falta.
    """
    d = date.fromisoformat(fecha)
    with connection() as conn, conn.cursor() as cur:
        _asegurar_particion(cur, d.year)
        cur.execute(SQL_CIERRE, {"sk": sk_fecha(d)})
        filas = cur.rowcount
        if filas == 0:
            conn.rollback()
            raise RuntimeError(f"No hay snapshots válidos para {fecha}; no se cerró el día")
        conn.commit()
    logger.info("Cierre de inventario %s: %s filas", fecha, filas)
    return filas
