"""Flujos orquestados con Prefect.

`flujo_catalogos` está IMPLEMENTADO y FUNCIONA como referencia: muestra
reintentos, paso de parámetros y encadenamiento de tareas. Los flujos de
ventas, inventario y cierre son tu entregable.

Si prefieres Airflow, Dagster u otra herramienta, mueve la implementación y
justifica la elección en docs/ORQUESTACION.md.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from prefect import flow, get_run_logger, task

from src.loaders.fact_loaders import SnapshotIncompleto
from src.pipelines import analytics, dimensiones, inventario, ventas
from src.utils.db import connection

TZ = ZoneInfo("America/Guatemala")


def _ahora() -> datetime:
    return datetime.now(TZ)


def _hoy_compacto() -> str:
    return _ahora().strftime("%Y%m%d")


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
def _reintentar(task, task_run, state) -> bool:  # noqa: ARG001
    """Un snapshot incompleto no se arregla reintentando: se alerta y se espera al siguiente."""
    try:
        state.result()
    except SnapshotIncompleto:
        return False
    except Exception:  # noqa: BLE001
        return True
    return False


def _alertar(flow, flow_run, state) -> None:  # noqa: ARG001
    """Hook de fallo. Hoy deja el mensaje en el log; en producción se sustituye por
    un webhook o una Automation de Prefect (Slack / correo)."""
    get_run_logger().error("ALERTA [%s] %s: %s", flow.name, flow_run.name, state.message)


@task
def verificar_catalogos() -> None:
    """No se cargan hechos con dimensiones viejas: exige dim_articulo y dim_tienda
    en EXITO en las últimas 30 h (si no, los códigos nuevos llegarían como huérfanos)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT count(DISTINCT flujo) FROM etl.ejecucion
                WHERE flujo IN ('dim_articulo', 'dim_tienda') AND estado = 'EXITO'
                  AND iniciado_en > now() - interval '30 hours'"""
        )
        n = cur.fetchone()[0]
    if n < 2:
        raise RuntimeError(
            "Catálogos sin actualizar en las últimas 30 h: no se cargan hechos "
            "con dimensiones viejas (corre flujo_catalogos primero)"
        )


@task(retries=3, retry_delay_seconds=300, timeout_seconds=1800)
def cargar_ventas_corte(fecha: str, corte: str) -> dict:
    """3 reintentos cada 5 min: el archivo del corte puede aterrizar tarde."""
    return ventas.ventas_intradia(fecha, corte).run()


@task(retries=2, retry_delay_seconds=30, retry_condition_fn=_reintentar, timeout_seconds=1200)
def cargar_inventario_snapshot(fecha: str, hora: str) -> dict:
    """timeout (20 min) < intervalo (30 min): una corrida colgada no acumula cola."""
    return inventario.inventario_intradia(fecha, hora).run()


@task
def cerrar_dia(fecha: str) -> int:
    return inventario.cerrar_inventario_dia(fecha)


@task
def verificar_sin_snapshots_en_curso() -> None:
    """El cierre no debe correr mientras un snapshot sigue cargándose."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT count(*) FROM etl.ejecucion
                WHERE flujo = 'fct_inventario_intradia' AND estado = 'EN_CURSO'
                  AND iniciado_en > now() - interval '30 minutes'"""
        )
        if cur.fetchone()[0]:
            raise RuntimeError("Hay un snapshot de inventario en curso; se reintenta el cierre")


@task(retries=2, retry_delay_seconds=60)
def refrescar_kpis(con_ventas: bool = True, con_inventario: bool = True) -> None:
    analytics.refrescar(ventas=con_ventas, inventario=con_inventario)


@flow(name="etl-ventas-intradia", on_failure=[_alertar], log_prints=True)
def flujo_ventas(
    fecha: str | None = None, corte: str = "0800", validar_catalogos: bool = True
) -> None:
    """Un corte de ventas (acumulado) + refresco de la MV de ventas.

    fecha 'AAAA-MM-DD' (por defecto hoy en Guatemala). Backfill: fecha y corte
    explícitos con validar_catalogos=False; el upsert es idempotente.
    """
    fecha = fecha or _ahora().strftime("%Y-%m-%d")
    if validar_catalogos:
        verificar_catalogos()
    met = cargar_ventas_corte(fecha, corte)
    refrescar_kpis(con_ventas=True, con_inventario=False)
    get_run_logger().info("Ventas %s %s: %s", fecha, corte, met)


@flow(name="etl-inventario-intradia", on_failure=[_alertar], log_prints=True)
def flujo_inventario(
    fecha: str | None = None, hora: str | None = None, validar_catalogos: bool = True
) -> None:
    """Snapshot de inventario. Sin hora: la franja de 30 min actual (HHMM)."""
    ahora = _ahora()
    fecha = fecha or ahora.strftime("%Y-%m-%d")
    hora = hora or f"{ahora.hour:02d}{'30' if ahora.minute >= 30 else '00'}"
    if validar_catalogos:
        verificar_catalogos()
    met = cargar_inventario_snapshot(fecha, hora)
    get_run_logger().info("Inventario %s %s: %s", fecha, hora, met)


@flow(name="etl-cierre-diario", on_failure=[_alertar], log_prints=True)
def flujo_cierre(fecha: str | None = None) -> None:
    """Cierre de inventario del día + refresco de TODAS las MV de KPIs.

    Sin fecha: cierra AYER (corre a las 00:30, después del snapshot de las 23:30).
    """
    fecha = fecha or (_ahora() - timedelta(days=1)).strftime("%Y-%m-%d")
    verificar_sin_snapshots_en_curso()
    filas = cerrar_dia(fecha)
    refrescar_kpis(con_ventas=True, con_inventario=True)
    get_run_logger().info("Cierre %s: %s filas", fecha, filas)


@flow(name="etl-refresco-kpis", on_failure=[_alertar], log_prints=True)
def flujo_refresco_kpis() -> None:
    """Red de seguridad: refresco completo diario por si algún refresco puntual falló."""
    refrescar_kpis(con_ventas=True, con_inventario=True)
