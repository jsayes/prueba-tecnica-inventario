"""Pruebas de las funciones de limpieza (implementadas como referencia).

Estas pasan tal cual. Se espera que agregues las tuyas para las
transformaciones de hechos: cálculo de medidas, manejo de devoluciones y
anulaciones, resolución de llaves surrogadas y deduplicación de snapshots.
"""
from datetime import date
from decimal import Decimal

import pytest

from src.transformers.cleaners import (
    a_booleano,
    a_decimal,
    a_fecha,
    a_timestamp,
    normalizar_codigo,
    sk_fecha,
)


@pytest.mark.parametrize("entrada", ["1", "true", "SI", "sí", "Y"])
def test_booleano_verdadero(entrada):
    assert a_booleano(entrada) is True


@pytest.mark.parametrize("entrada", ["0", "false", "NO", "n"])
def test_booleano_falso(entrada):
    assert a_booleano(entrada) is False


def test_booleano_vacio_es_none():
    """Un vacío es ausencia de dato, no un False. El loader decide el default."""
    assert a_booleano("") is None


def test_booleano_invalido():
    with pytest.raises(ValueError):
        a_booleano("quizás")


def test_decimal_con_moneda_y_miles():
    assert a_decimal("Q 1,234.56") == Decimal("1234.56")


def test_decimal_vacio_es_none():
    assert a_decimal("") is None


def test_fecha_formatos_mixtos():
    assert a_fecha("2026-03-02") == a_fecha("02/03/2026") == date(2026, 3, 2)


def test_timestamp_formato_alterno():
    assert a_timestamp("02/03/2026 14:30").hour == 14


def test_normalizar_codigo():
    assert normalizar_codigo("  t006 ") == "T006"


def test_sk_fecha():
    assert sk_fecha(date(2026, 3, 2)) == 20260302
