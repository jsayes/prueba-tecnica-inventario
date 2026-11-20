"""Flujos orquestados con Prefect.

`flujo_catalogos` está IMPLEMENTADO y FUNCIONA como referencia: muestra
reintentos, paso de parámetros y encadenamiento de tareas. Los flujos de
ventas, inventario y cierre son tu entregable.

Si prefieres Airflow, Dagster u otra herramienta, mueve la implementación y
justifica la elección en docs/ORQUESTACION.md.
"""
from __future__ import annotations

from datetime import datetime

from prefect import flow, get_run_logger, task

from src.pipelines import dimensiones, inventario, ventas


def _hoy_compacto() -> str:
    return datetime.now().strftime("%Y%m%d")


# ---------------------------------------------------------------------------
# IMPLEMENTADO — referencia
# ---------------------------------------------------------------------------
@task(retries=3, retry_delay_seconds=60, task_run_name="dim-articulo-{fecha_archivo}")
def cargar_dim_articulo(fecha_archivo: str) -> dict:
    return dimensiones.dim_articulo(fecha_archivo).run()


@task(retries=3, retry_delay_seconds=60, task_run_name="dim-tienda-{fecha_archivo}")
def cargar_dim_tienda(fecha_archivo: str) -> dict:
    return dimensiones.dim_tienda(fecha_archivo).run()


@flow(name="etl-catalogos", log_prints=True)
def flujo_catalogos(fecha_archivo: str | None = None) -> None:
    """Refresca las dimensiones. Debe correr ANTES de los hechos del día."""
    fecha_archivo = fecha_archivo or _hoy_compacto()
    logger = get_run_logger()
    art = cargar_dim_articulo(fecha_archivo)
    tie = cargar_dim_tienda(fecha_archivo)
    logger.info("Catálogos al día: articulos=%s tiendas=%s", art, tie)


# ---------------------------------------------------------------------------
# TODO (candidato)
# ---------------------------------------------------------------------------
@task(retries=3, retry_delay_seconds=60)
def cargar_ventas_corte(fecha: str, corte: str) -> dict:
    """TODO: invocar ventas.ventas_intradia(fecha, corte).run()."""
    raise NotImplementedError


@task(retries=2, retry_delay_seconds=30)
def cargar_inventario_snapshot(fecha: str, hora: str) -> dict:
    """TODO: invocar inventario.inventario_intradia(fecha, hora).run()."""
    raise NotImplementedError


@flow(name="etl-ventas-intradia")
def flujo_ventas(fecha: str | None = None, corte: str = "0800") -> None:
    """TODO: corre 3 veces al día. Decide si depende de flujo_catalogos."""
    raise NotImplementedError


@flow(name="etl-inventario-intradia")
def flujo_inventario(fecha: str | None = None, hora: str | None = None) -> None:
    """TODO: corre cada 30 minutos. Cuida el solapamiento entre ejecuciones."""
    raise NotImplementedError


@flow(name="etl-cierre-diario")
def flujo_cierre(fecha: str | None = None) -> None:
    """TODO: cierre de inventario + refresco de las vistas materializadas."""
    raise NotImplementedError
