"""Validaciones de calidad.

El motor y las reglas de ventas están IMPLEMENTADOS como referencia. Las de
inventario son tu entregable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Callable, Iterable

Regla = tuple[str, Callable[[dict], bool]]


@dataclass
class ResultadoValidacion:
    validos: list[dict] = field(default_factory=list)
    rechazados: list[tuple[dict, str]] = field(default_factory=list)

    @property
    def resumen(self) -> dict:
        total = len(self.validos) + len(self.rechazados)
        return {
            "validos": len(self.validos),
            "rechazados": len(self.rechazados),
            "ratio_rechazo": round(len(self.rechazados) / total, 4) if total else 0.0,
        }


class Validador:
    def __init__(self, reglas: list[Regla], max_reject_ratio: float | None = None) -> None:
        self.reglas = reglas
        self.max_reject_ratio = max_reject_ratio

    def run(self, records: Iterable[dict]) -> ResultadoValidacion:
        res = ResultadoValidacion()
        for r in records:
            for nombre, regla in self.reglas:
                try:
                    ok = regla(r)
                except Exception:
                    ok = False
                if not ok:
                    res.rechazados.append((r, nombre))
                    break
            else:
                res.validos.append(r)

        if self.max_reject_ratio is not None and res.resumen["ratio_rechazo"] > self.max_reject_ratio:
            raise RuntimeError(
                f"Ratio de rechazo {res.resumen['ratio_rechazo']} supera el máximo "
                f"permitido {self.max_reject_ratio}"
            )
        return res


# ---------------------------------------------------------------------------
# Reglas de ventas — IMPLEMENTADAS COMO REFERENCIA
# ---------------------------------------------------------------------------
ESTADOS_VENTA = {"CONFIRMADA", "ANULADA", "DEVOLUCION"}


def _no_nulo(*campos: str) -> Callable[[dict], bool]:
    return lambda r: all(r.get(c) is not None for c in campos)


REGLAS_VENTA: list[Regla] = [
    ("llave_natural_completa", _no_nulo("id_transaccion", "linea")),
    ("fecha_valida", lambda r: r.get("fecha_hora") is not None),
    ("fecha_no_futura", lambda r: r["fecha_hora"] <= datetime.now()),
    ("estado_en_dominio", lambda r: r.get("estado") in ESTADOS_VENTA),
    ("articulo_existe_en_dimension", _no_nulo("sk_articulo")),
    ("tienda_existe_en_dimension", _no_nulo("sk_tienda")),
    ("unidades_distintas_de_cero", lambda r: r.get("unidades") not in (None, Decimal(0))),
    (
        "unidades_negativas_solo_en_devolucion",
        lambda r: r["unidades"] > 0 or r["estado"] == "DEVOLUCION",
    ),
    ("precio_no_negativo", lambda r: r.get("precio_unitario") is None or r["precio_unitario"] >= 0),
]


# ---------------------------------------------------------------------------
# TODO (candidato): reglas de inventario. Mínimo esperado:
#   - llave natural completa (sk_fecha, hora_snapshot, sk_tienda, sk_articulo)
#   - artículo y tienda existen en la dimensión vigente
#   - unidades_disponibles no nula; definir el criterio para negativas
#     (¿se rechaza el registro o se trunca a cero?) y documentarlo
#   - costo_promedio no negativo
# ---------------------------------------------------------------------------
REGLAS_INVENTARIO: list[Regla] = [
    ("llave_natural_completa",
     _no_nulo("sk_fecha", "hora_snapshot", "codigo_tienda", "codigo_articulo")),
    ("articulo_existe_en_dimension", _no_nulo("sk_articulo")),
    ("tienda_existe_en_dimension", _no_nulo("sk_tienda")),
    ("unidades_disponibles_no_nula", _no_nulo("unidades_disponibles")),
    ("unidades_disponibles_no_negativas", lambda r: r["unidades_disponibles"] >= 0),
    ("transito_y_comprometidas_no_negativas",
     lambda r: r["unidades_transito"] >= 0 and r["unidades_comprometidas"] >= 0),
    ("costo_promedio_no_negativo",
     lambda r: r.get("costo_promedio") is None or r["costo_promedio"] >= 0),
]

## Decisión sobre unidades negativas: se rechazan a cuarentena, no
# se truncan a cero. Truncar oculta una falla del origen y falsea el valor del
# inventario y la tasa de stockouts (un -5 convertido en 0 parece "agotado").
# El orden importa: las de nulidad van primero porque el Validador trata una
# excepción como rechazo y las comparaciones asumen valores no nulos