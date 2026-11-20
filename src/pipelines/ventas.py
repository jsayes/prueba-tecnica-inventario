"""Flujos de ventas.

`ventas_historico` está IMPLEMENTADO como referencia completa: control de
archivo ya procesado, extracción, transformación, validación y carga única.

`ventas_intradia` es tu entregable.
"""
from __future__ import annotations

from src.config.settings import PROJECT_ROOT, load_config, source_config
from src.extractors.csv_extractor import build_extractor
from src.loaders.fact_loaders import FullOnceLoader
from src.pipelines.pipeline import Pipeline
from src.quality.rules import REGLAS_VENTA, Validador
from src.transformers.base import Chain
from src.transformers.facts import DimensionResolver, VentaTransformer
from src.transformers.generic import Deduplicate
from src.utils.db import file_hash
from src.utils.logger import get_logger
from src.utils.run_tracker import archivo_ya_procesado, marcar_archivo_procesado

logger = get_logger(__name__)

COLUMNAS_VENTA = [
    "id_transaccion", "linea", "sk_fecha", "fecha_hora", "sk_tienda", "sk_articulo",
    "unidades", "precio_unitario", "descuento", "costo_unitario", "venta_neta",
    "costo_total", "estado", "canal", "fecha_actualizacion",
]


def ventas_historico(anio: int) -> Pipeline:
    """Carga única del histórico de un año. IMPLEMENTADO."""
    nombre = "fct_venta_historico"
    cfg = source_config(nombre)
    ruta = PROJECT_ROOT / cfg["path_pattern"].format(anio=anio)

    if archivo_ya_procesado(nombre, ruta.name, file_hash(ruta)):
        logger.info("%s ya fue procesado; nada que hacer", ruta.name)
        return _pipeline_vacio(nombre, {"anio": anio})

    quality = load_config()["quality"]
    pipeline = Pipeline(
        nombre=nombre,
        extractor=build_extractor(cfg["extractor"], path=ruta),
        transformer=Chain(
            VentaTransformer(DimensionResolver().cargar()),
            Deduplicate(cfg["natural_key"]),
        ),
        loader=FullOnceLoader(cfg["target"], cfg["natural_key"], COLUMNAS_VENTA),
        validador=Validador(REGLAS_VENTA, quality.get("max_reject_ratio")),
        parametros={"anio": anio},
    )

    _al_terminar(pipeline, nombre, ruta)
    return pipeline


def ventas_intradia(fecha: str, corte: str) -> Pipeline:
    """Carga de un corte intradía. TODO — a implementar.

    corte: '0800' | '1400' | '2000'. Cada corte es acumulado del día.
    Reutiliza VentaTransformer, REGLAS_VENTA y el patrón de `ventas_historico`;
    lo que cambia es el loader (UpsertLoader) y el criterio de conflicto.
    """
    raise NotImplementedError("TODO: implementar")


# --------------------------------------------------------------------------
# utilidades internas del template
# --------------------------------------------------------------------------
def _pipeline_vacio(nombre: str, parametros: dict) -> Pipeline:
    from src.extractors.base import BaseExtractor
    from src.loaders.base import BaseLoader
    from src.transformers.base import BaseTransformer

    class _Nada(BaseExtractor, BaseTransformer, BaseLoader):
        def __init__(self):
            BaseLoader.__init__(self, "-", [])

        def extract(self):
            return iter(())

        def transform(self, records):
            return iter(records)

        def load(self, records):
            return 0

    nada = _Nada()
    return Pipeline(nombre, nada, nada, nada, parametros=parametros)


def _al_terminar(pipeline: Pipeline, flujo: str, ruta) -> None:
    """Envuelve run() para registrar el archivo procesado tras un éxito."""
    original = pipeline.run

    def run():
        metricas = original()
        marcar_archivo_procesado(flujo, ruta.name, file_hash(ruta), metricas["cargadas"])
        return metricas

    pipeline.run = run  # type: ignore[method-assign]
