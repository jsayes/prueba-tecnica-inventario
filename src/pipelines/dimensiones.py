"""Flujos de dimensiones. IMPLEMENTADOS COMO REFERENCIA.

Úsalos como plantilla para construir los flujos de hechos.
"""
from __future__ import annotations

from src.config.settings import PROJECT_ROOT, source_config
from src.extractors.csv_extractor import build_extractor
from src.loaders.scd2_loader import SCD2Loader
from src.pipelines.pipeline import Pipeline
from src.transformers.base import Chain
from src.transformers.generic import ConfigurableTransformer, Deduplicate

COLUMNAS_ARTICULO = [
    "codigo_articulo", "descripcion", "codigo_categoria", "categoria", "subcategoria",
    "marca", "unidad_medida", "costo_estandar", "precio_lista", "en_modelo", "activo",
]
COLUMNAS_TIENDA = [
    "codigo_tienda", "nombre_tienda", "departamento", "region", "formato",
    "es_centro_distribucion", "activa_modelo", "metros_cuadrados", "fecha_apertura",
]


def _build(nombre: str, fecha_archivo: str, columnas: list[str]) -> Pipeline:
    cfg = source_config(nombre)
    ruta = PROJECT_ROOT / cfg["path_pattern"].format(fecha_archivo=fecha_archivo)
    extractor = build_extractor(cfg["extractor"], path=ruta)
    transformer = Chain(
        ConfigurableTransformer(cfg.get("transform", {})),
        Deduplicate(cfg["natural_key"]),
    )
    loader = SCD2Loader(
        target=cfg["target"],
        natural_key=cfg["natural_key"],
        tracked_columns=cfg["tracked_columns"],
        columns=columnas,
    )
    return Pipeline(nombre, extractor, transformer, loader, parametros={"fecha_archivo": fecha_archivo})


def dim_articulo(fecha_archivo: str) -> Pipeline:
    return _build("dim_articulo", fecha_archivo, COLUMNAS_ARTICULO)


def dim_tienda(fecha_archivo: str) -> Pipeline:
    return _build("dim_tienda", fecha_archivo, COLUMNAS_TIENDA)
