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


class UpsertLoader(BaseLoader):
    """Carga incremental con resolución de conflictos. TODO — a implementar.

    Requisitos:
      · ON CONFLICT sobre la llave natural.
      · El UPDATE debe aplicarse solo si la fecha_actualizacion entrante es
        mayor o igual a la almacenada (cláusula WHERE en el DO UPDATE).
      · Debe devolver la cantidad de filas realmente afectadas.

    Pista: `FullOnceLoader` ya arma el INSERT; aquí cambia la cláusula de
    conflicto. Revisa cómo se comporta `executemany` cuando el mismo lote trae
    la llave repetida.
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

    def load(self, records: Iterable[dict]) -> int:
        raise NotImplementedError("TODO: implementar")
