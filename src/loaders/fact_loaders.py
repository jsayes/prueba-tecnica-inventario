"""Loaders de hechos.

`FullOnceLoader` está IMPLEMENTADO como referencia: es el patrón de carga única
idempotente (control por archivo + hash, e `ON CONFLICT DO NOTHING` sobre la
llave natural).

`SnapshotLoader` está IMPLEMENTADO: resuelve la carga del snapshot de
inventario (reemplazo idempotente del alcance del snapshot).

`UpsertLoader` es tu entregable. Es el que sostiene el flujo de ventas
intradía y es donde está la dificultad real del caso:

  VENTAS — 3 cortes por día (08:00, 14:00, 20:00)
    · Cada corte es ACUMULADO del día, no un delta: el segundo reenvía lo que
      ya trajo el primero.
    · El origen corrige: una venta puede llegar CONFIRMADA en un corte y
      ANULADA en el siguiente, o cambiar de unidades. Gana la versión con
      fecha_actualizacion más reciente, sin importar el orden en que lleguen
      los archivos.
    · Hay ventas que llegan tarde: registros con fecha_hora de un día anterior
      aparecen en el corte de hoy.

"""
from __future__ import annotations

from typing import Iterable, Sequence

from src.loaders.base import BaseLoader
from src.utils.db import connection
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FullOnceLoader(BaseLoader):
    """Carga única, idempotente. IMPLEMENTADO COMO REFERENCIA.

    La idempotencia es doble:
      1. el pipeline no vuelve a leer un archivo ya registrado en
         etl.archivo_procesado (ver src/pipelines/ventas.py);
      2. la inserción usa ON CONFLICT DO NOTHING sobre la llave natural, así
         que un reproceso parcial tampoco duplica.
    """

    def __init__(self, target: str, natural_key: list[str], columns: Sequence[str]) -> None:
        super().__init__(target, natural_key)
        self.columns = list(columns)

    def load(self, records: Iterable[dict]) -> int:
        filas = [tuple(r.get(c) for c in self.columns) for r in records]
        if not filas:
            return 0

        cols = ", ".join(self.columns)
        placeholders = ", ".join(["%s"] * len(self.columns))
        conflicto = ", ".join(self.natural_key)
        sql = (
            f"INSERT INTO {self.target} ({cols}) VALUES ({placeholders}) "  # noqa: S608
            f"ON CONFLICT ({conflicto}) DO NOTHING"
        )

        with connection() as conn:
            with conn.cursor() as cur:
                for i in range(0, len(filas), 5000):
                    cur.executemany(sql, filas[i : i + 5000])
            conn.commit()

        logger.info("%s: %s filas enviadas", self.target, len(filas))
        return len(filas)


class SnapshotLoader(BaseLoader):
    """Carga de un snapshot completo. IMPLEMENTADO COMO REFERENCIA.

    El snapshot de inventario es una fotografía de un instante: reemplazar su
    alcance (fecha + hora) es la operación natural y hace la carga idempotente
    sin necesidad de resolver conflictos fila por fila. Todo ocurre en una
    transacción.

    Compáralo con el caso de ventas: ahí los cortes son ACUMULADOS y el origen
    corrige registros individuales, así que reemplazar el alcance perdería la
    información de qué versión es la más reciente. Por eso ventas necesita
    upsert y esto no.
    """

    def __init__(
        self,
        target: str,
        natural_key: list[str],
        columns: Sequence[str],
        scope_columns: Sequence[str],
    ) -> None:
        super().__init__(target, natural_key)
        self.columns = list(columns)
        self.scope_columns = list(scope_columns)

    def load(self, records: Iterable[dict]) -> int:
        filas = [tuple(r.get(c) for c in self.columns) for r in records]
        if not filas:
            logger.warning("%s: el snapshot llegó vacío; no se carga nada", self.target)
            return 0

        primero = records[0] if isinstance(records, list) else None
        alcance = {c: (primero or {}).get(c) for c in self.scope_columns}
        if any(v is None for v in alcance.values()):
            raise ValueError(f"No se pudo determinar el alcance del snapshot: {alcance}")

        where = " AND ".join(f"{c} = %s" for c in self.scope_columns)
        cols = ", ".join(self.columns)
        placeholders = ", ".join(["%s"] * len(self.columns))

        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self.target} WHERE {where}",  # noqa: S608
                    tuple(alcance[c] for c in self.scope_columns),
                )
                borradas = cur.rowcount
                for i in range(0, len(filas), 5000):
                    cur.executemany(
                        f"INSERT INTO {self.target} ({cols}) VALUES ({placeholders})",  # noqa: S608
                        filas[i : i + 5000],
                    )
            conn.commit()

        logger.info(
            "%s alcance %s: %s borradas, %s insertadas",
            self.target, alcance, borradas, len(filas),
        )
        return len(filas)


class SnapshotIncompleto(Exception):
    """El snapshot no alcanza el umbral de completitud: se descarta completo."""


def resolver_lote(records: Iterable[dict], natural_key: Sequence[str], update_column: str) -> list[dict]:
    """Una fila por llave natural: gana la de mayor `update_column`.

    Empate: gana la última vista (un corte posterior reemplaza a uno anterior).
    El resultado no depende del orden de llegada de las versiones.
    """
    mejores: dict[tuple, dict] = {}
    for r in records:
        k = tuple(r.get(c) for c in natural_key)
        prev = mejores.get(k)
        if prev is None or r[update_column] >= prev[update_column]:
            mejores[k] = r
    return list(mejores.values())


class UpsertLoader(BaseLoader):
    """Carga incremental con resolución de conflictos.

    · ON CONFLICT sobre la llave natural.
    · El UPDATE solo se aplica si la fecha entrante es mayor o igual a la
      almacenada (no retrocede ante cortes reenviados fuera de orden) Y el
      contenido realmente cambia (IS DISTINCT FROM): reejecutar un corte
      idéntico afecta 0 filas y no reescribe `fecha_carga`.
    · El lote se resuelve en Python antes de enviarlo, para no depender del
      orden de `executemany` cuando el lote trae la llave repetida.
    · Devuelve las filas realmente afectadas (insertadas + actualizadas).
    """

    def __init__(
        self,
        target: str,
        natural_key: list[str],
        columns: Sequence[str],
        update_column: str = "fecha_actualizacion",
    ) -> None:
        super().__init__(target, natural_key)
        self.columns = list(columns)
        self.update_column = update_column

    def _sql(self) -> str:
        cols = ", ".join(self.columns)
        placeholders = ", ".join(["%s"] * len(self.columns))
        conflicto = ", ".join(self.natural_key)
        mutables = [c for c in self.columns if c not in self.natural_key]
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in mutables)
        actual = ", ".join(f"{self.target}.{c}" for c in mutables)
        entrante = ", ".join(f"EXCLUDED.{c}" for c in mutables)
        return (
            f"INSERT INTO {self.target} ({cols}) VALUES ({placeholders}) "  # noqa: S608
            f"ON CONFLICT ({conflicto}) DO UPDATE SET {sets}, fecha_carga = now() "
            f"WHERE {self.target}.{self.update_column} <= EXCLUDED.{self.update_column} "
            f"AND ({actual}) IS DISTINCT FROM ({entrante})"
        )

    def load(self, records: Iterable[dict]) -> int:
        lote = resolver_lote(records, self.natural_key, self.update_column)
        filas = [tuple(r.get(c) for c in self.columns) for r in lote]
        if not filas:
            return 0

        sql = self._sql()
        afectadas = 0
        with connection() as conn:
            with conn.cursor() as cur:
                for fila in filas:
                    # Una sentencia por fila: rowcount es exacto (0 = ignorada por
                    # fecha vieja o sin cambios). executemany no garantiza el total.
                    cur.execute(sql, fila)
                    afectadas += max(cur.rowcount, 0)
            conn.commit()

        logger.info(
            "%s: %s filas en el lote, %s insertadas/actualizadas",
            self.target, len(filas), afectadas,
        )
        return afectadas


class SnapshotCompletoLoader(BaseLoader):
    """Envuelve a un SnapshotLoader y NO carga nada si el snapshot es incompleto.

    Esperado = filas del último cierre diario previo (con fallback configurable).
    Decisión: se descarta completo (todo o nada) y se lanza SnapshotIncompleto,
    para que el cierre y los stockouts nunca lean un día con tiendas faltantes.
    """

    def __init__(
        self,
        inner: SnapshotLoader,
        min_ratio: float = 0.95,
        fallback_esperadas: int = 1080,
    ) -> None:
        super().__init__(inner.target, inner.natural_key)
        self.inner = inner
        self.min_ratio = min_ratio
        self.fallback_esperadas = fallback_esperadas

    def _esperadas(self, sk_fecha: int) -> int:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT count(*) FROM core.fct_inventario_diario
                    WHERE sk_fecha = (SELECT max(sk_fecha) FROM core.fct_inventario_diario
                                       WHERE sk_fecha < %s)""",
                (sk_fecha,),
            )
            n = cur.fetchone()[0]
        return n or self.fallback_esperadas

    def load(self, records: Iterable[dict]) -> int:
        registros = list(records)
        if not registros:
            raise SnapshotIncompleto("SNAPSHOT_INCOMPLETO: snapshot vacío")
        esperadas = self._esperadas(registros[0]["sk_fecha"])
        if len(registros) < esperadas * self.min_ratio:
            raise SnapshotIncompleto(
                f"SNAPSHOT_INCOMPLETO: {len(registros)}/{esperadas} filas "
                f"(mínimo {self.min_ratio:.0%}); no se carga"
            )
        return self.inner.load(registros)

