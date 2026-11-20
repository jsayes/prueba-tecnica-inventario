
from __future__ import annotations

from src.utils.db import connection
from src.utils.logger import get_logger

logger = get_logger(__name__)


def refrescar(ventas: bool = True, inventario: bool = True) -> None:
    """Refresca las vistas materializadas de KPIs (CONCURRENTLY: sin bloquear lecturas)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT analytics.refrescar(%s, %s)", (ventas, inventario))
        conn.commit()
    logger.info("analytics refrescado (ventas=%s, inventario=%s)", ventas, inventario)
