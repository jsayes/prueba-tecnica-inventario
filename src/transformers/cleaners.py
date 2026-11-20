"""Funciones de limpieza reutilizables. Implementadas como referencia.

Las fuentes traen: espacios sobrantes, mayúsculas inconsistentes, booleanos en
seis representaciones distintas, símbolo de moneda, separador de miles y
fechas en dos formatos. Estas funciones resuelven esos casos y son la base
sobre la que debes construir las transformaciones de los hechos.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

VERDADEROS = {"1", "true", "t", "si", "sí", "s", "yes", "y"}
FALSOS = {"0", "false", "f", "no", "n"}

FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y")
FORMATOS_TIMESTAMP = ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%S")


def limpiar_texto(valor) -> str | None:
    if valor is None:
        return None
    v = str(valor).strip()
    return v or None


def normalizar_codigo(valor) -> str | None:
    """Códigos de negocio: sin espacios y en mayúsculas."""
    v = limpiar_texto(valor)
    return v.upper() if v else None


def a_booleano(valor) -> bool | None:
    v = limpiar_texto(valor)
    if v is None:
        return None
    v = v.lower()
    if v in VERDADEROS:
        return True
    if v in FALSOS:
        return False
    raise ValueError(f"Valor booleano no reconocido: {valor!r}")


def a_decimal(valor) -> Decimal | None:
    """Acepta '1,234.56', 'Q 1,234.56', '', None."""
    v = limpiar_texto(valor)
    if v is None:
        return None
    v = v.replace("Q", "").replace("$", "").replace(",", "").strip()
    if not v:
        return None
    try:
        return Decimal(v)
    except InvalidOperation as exc:
        raise ValueError(f"Valor numérico inválido: {valor!r}") from exc


def a_fecha(valor) -> date | None:
    v = limpiar_texto(valor)
    if v is None:
        return None
    for fmt in FORMATOS_FECHA:
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha no parseable: {valor!r}")


def a_timestamp(valor) -> datetime | None:
    v = limpiar_texto(valor)
    if v is None:
        return None
    for fmt in FORMATOS_TIMESTAMP:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    raise ValueError(f"Timestamp no parseable: {valor!r}")


def sk_fecha(valor: date | datetime) -> int:
    d = valor.date() if isinstance(valor, datetime) else valor
    return int(d.strftime("%Y%m%d"))
