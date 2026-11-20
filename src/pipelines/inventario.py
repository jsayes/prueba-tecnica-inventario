"""Flujos de inventario.

`inventario_historico` está IMPLEMENTADO como referencia. Los flujos intradía
y el cierre diario son tu entregable.
"""
from __future__ import annotations

from src.config.settings import PROJECT_ROOT, load_config, source_config
from src.extractors.csv_extractor import build_extractor
from src.loaders.fact_loaders import FullOnceLoader
from src.pipelines.pipeline import Pipeline
from src.pipelines.ventas import _al_terminar, _pipeline_vacio
from src.quality.rules import REGLAS_INVENTARIO, Validador
from src.transformers.base import Chain
from src.transformers.facts import DimensionResolver, InventarioTransformer
from src.transformers.generic import Deduplicate
from src.utils.db import file_hash
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


def inventario_intradia(fecha: str, hora: str) -> Pipeline:
    """Carga de un snapshot de 30 minutos. hora: 'HHMM'. TODO — a implementar.

    Reutiliza InventarioTransformer y el patrón de `inventario_historico`; lo
    que cambia es el destino (core.fct_inventario_intradia), el loader
    (UpsertLoader) y la validación de completitud del snapshot.
    """
    raise NotImplementedError("TODO: implementar")


def cerrar_inventario_dia(fecha: str) -> None:
    """Deriva el cierre diario del último snapshot válido del día.

    TODO — a implementar. Es un paso SQL: leer core.fct_inventario_intradia,
    tomar la hora_snapshot máxima del día e insertar en
    core.fct_inventario_diario de forma idempotente (reejecutarlo debe dejar el
    mismo resultado).
    """
    raise NotImplementedError("TODO: implementar")
