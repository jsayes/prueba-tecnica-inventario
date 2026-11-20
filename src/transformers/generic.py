"""Transformer configurable por YAML. Implementado como referencia.

Lee el bloque `transform` de config.yaml y aplica las conversiones declaradas.
Sirve para las dimensiones; para los hechos probablemente necesites
transformers propios (cálculo de medidas, resolución de llaves surrogadas,
manejo de estados y devoluciones).
"""
from __future__ import annotations

from typing import Iterable, Iterator

from src.transformers.base import BaseTransformer
from src.transformers.cleaners import (
    a_booleano,
    a_decimal,
    a_fecha,
    limpiar_texto,
    normalizar_codigo,
)


class ConfigurableTransformer(BaseTransformer):
    def __init__(self, spec: dict) -> None:
        self.spec = spec or {}

    def transform(self, records: Iterable[dict]) -> Iterator[dict]:
        trim_all = self.spec.get("trim") == "*"
        numeric = self.spec.get("numeric", [])
        boolean = self.spec.get("boolean", [])
        fechas = self.spec.get("date", [])
        upper = self.spec.get("upper", [])
        rename = self.spec.get("rename", {})

        for r in records:
            out = dict(r)
            if trim_all:
                out = {k: (limpiar_texto(v) if isinstance(v, str) else v) for k, v in out.items()}
            for c in upper:
                if c in out:
                    out[c] = normalizar_codigo(out[c])
            for c in numeric:
                if c in out:
                    out[c] = a_decimal(out[c])
            for c in boolean:
                if c in out:
                    out[c] = a_booleano(out[c])
            for c in fechas:
                if c in out:
                    out[c] = a_fecha(out[c])
            for origen, destino in rename.items():
                if origen in out and origen != destino:
                    out[destino] = out.pop(origen)
            yield out


class Deduplicate(BaseTransformer):
    """Deduplica por llave natural conservando el último registro visto.

    Los archivos traen duplicados exactos y duplicados con diferencias. El
    criterio de sobrevivencia por defecto es "último gana"; si tu caso necesita
    otro (por ejemplo, el de mayor fecha_actualizacion), extiende esta clase y
    documéntalo.
    """

    def __init__(self, key: list[str]) -> None:
        self.key = key

    def transform(self, records: Iterable[dict]) -> Iterator[dict]:
        vistos: dict[tuple, dict] = {}
        for r in records:
            k = tuple(r.get(c) for c in self.key)
            vistos[k] = r
        yield from vistos.values()
