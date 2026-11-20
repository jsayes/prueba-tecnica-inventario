"""Transformaciones de hechos. IMPLEMENTADAS COMO REFERENCIA.

Incluyen la resolución de llaves surrogadas contra la versión vigente de las
dimensiones y el cálculo de medidas derivadas. Los flujos intradía que debes
implementar reutilizan estas mismas piezas: no deberías necesitar reescribirlas.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Iterator

from src.transformers.base import BaseTransformer
from src.transformers.cleaners import (
    a_decimal,
    a_fecha,
    a_timestamp,
    normalizar_codigo,
    sk_fecha,
)
from src.utils.db import connection
from src.utils.logger import get_logger

logger = get_logger(__name__)

ESTADOS_VENTA = {"CONFIRMADA", "ANULADA", "DEVOLUCION"}


class DimensionResolver:
    """Mapea código natural -> llave surrogada de la versión vigente.

    Se carga una vez por ejecución. Si un código no existe, el registro se
    marca con sk = None y la validación lo manda a cuarentena.
    """

    def __init__(self) -> None:
        self.articulos: dict[str, int] = {}
        self.tiendas: dict[str, int] = {}

    def cargar(self) -> "DimensionResolver":
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT codigo_articulo, sk_articulo FROM core.dim_articulo WHERE es_vigente"
            )
            self.articulos = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute(
                "SELECT codigo_tienda, sk_tienda FROM core.dim_tienda WHERE es_vigente"
            )
            self.tiendas = {r[0]: r[1] for r in cur.fetchall()}
        logger.info(
            "Dimensiones vigentes: %s artículos, %s tiendas",
            len(self.articulos),
            len(self.tiendas),
        )
        return self


class VentaTransformer(BaseTransformer):
    """Normaliza una línea de venta y calcula sus medidas."""

    def __init__(self, resolver: DimensionResolver) -> None:
        self.resolver = resolver

    def transform(self, records: Iterable[dict]) -> Iterator[dict]:
        for r in records:
            cod_art = normalizar_codigo(r.get("codigo_articulo"))
            cod_tie = normalizar_codigo(r.get("codigo_tienda"))
            fecha_hora = a_timestamp(r.get("fecha_hora"))
            unidades = a_decimal(r.get("unidades")) or Decimal(0)
            precio = a_decimal(r.get("precio_unitario"))
            descuento = a_decimal(r.get("descuento")) or Decimal(0)
            costo = a_decimal(r.get("costo_unitario"))
            estado = (r.get("estado") or "").strip().upper()

            yield {
                "id_transaccion": normalizar_codigo(r.get("id_transaccion")),
                "linea": int(r["linea"]) if r.get("linea") not in (None, "") else None,
                "sk_fecha": sk_fecha(fecha_hora) if fecha_hora else None,
                "fecha_hora": fecha_hora,
                "sk_tienda": self.resolver.tiendas.get(cod_tie),
                "sk_articulo": self.resolver.articulos.get(cod_art),
                "codigo_tienda": cod_tie,
                "codigo_articulo": cod_art,
                "unidades": unidades,
                "precio_unitario": precio,
                "descuento": descuento,
                "costo_unitario": costo,
                "venta_neta": (unidades * precio - descuento) if precio is not None else None,
                "costo_total": (unidades * costo) if costo is not None else None,
                "estado": estado if estado in ESTADOS_VENTA else estado,
                "canal": (r.get("canal") or "").strip().upper() or None,
                "fecha_actualizacion": a_timestamp(r.get("fecha_actualizacion")) or fecha_hora,
            }


class InventarioTransformer(BaseTransformer):
    """Normaliza una fila de inventario y calcula el valor de la existencia."""

    def __init__(self, resolver: DimensionResolver) -> None:
        self.resolver = resolver

    def transform(self, records: Iterable[dict]) -> Iterator[dict]:
        for r in records:
            cod_art = normalizar_codigo(r.get("codigo_articulo"))
            cod_tie = normalizar_codigo(r.get("codigo_tienda"))
            fecha = a_fecha(r.get("fecha_snapshot"))
            disponibles = a_decimal(r.get("unidades_disponibles"))
            costo_prom = a_decimal(r.get("costo_promedio"))

            yield {
                "sk_fecha": sk_fecha(fecha) if fecha else None,
                "fecha_snapshot": fecha,
                "hora_snapshot": (r.get("hora_snapshot") or "").strip() or None,
                "sk_tienda": self.resolver.tiendas.get(cod_tie),
                "sk_articulo": self.resolver.articulos.get(cod_art),
                "codigo_tienda": cod_tie,
                "codigo_articulo": cod_art,
                "unidades_disponibles": disponibles,
                "unidades_transito": a_decimal(r.get("unidades_transito")) or Decimal(0),
                "unidades_comprometidas": a_decimal(r.get("unidades_comprometidas")) or Decimal(0),
                "costo_promedio": costo_prom,
                "valor_inventario": (disponibles * costo_prom)
                if disponibles is not None and costo_prom is not None
                else None,
                "fecha_actualizacion": a_timestamp(r.get("fecha_actualizacion")),
            }
