"""Loader SCD tipo 2 para dimensiones. IMPLEMENTADO COMO REFERENCIA.

Este es el patrón que se espera que reutilices y adaptes: comparación por
hash de atributos versionados, cierre de la versión anterior y apertura de la
nueva, todo en una sola transacción e idempotente (si nada cambió, no escribe).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from src.loaders.base import BaseLoader
from src.utils.db import attribute_hash, connection
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SCD2Loader(BaseLoader):
    def __init__(
        self,
        target: str,
        natural_key: list[str],
        tracked_columns: list[str],
        columns: list[str],
        vigencia: datetime | None = None,
    ) -> None:
        super().__init__(target, natural_key)
        self.tracked_columns = tracked_columns
        self.columns = columns
        self.vigencia = vigencia or datetime.now(timezone.utc)

    def load(self, records: Iterable[dict]) -> int:
        registros = list(records)
        if not registros:
            return 0

        nk = self.natural_key[0]
        afectados = 0

        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {nk}, hash_atributos FROM {self.target} WHERE es_vigente"  # noqa: S608
                )
                vigentes = {row[0]: row[1] for row in cur.fetchall()}

                nuevos, cambiados = [], []
                for r in registros:
                    clave = r[nk]
                    h = attribute_hash(r, self.tracked_columns)
                    r["hash_atributos"] = h
                    if clave not in vigentes:
                        nuevos.append(r)
                    elif vigentes[clave] != h:
                        cambiados.append(r)

                if cambiados:
                    cur.executemany(
                        f"""UPDATE {self.target}
                               SET valido_hasta = %s, es_vigente = FALSE
                             WHERE {nk} = %s AND es_vigente""",  # noqa: S608
                        [(self.vigencia, r[nk]) for r in cambiados],
                    )

                a_insertar = nuevos + cambiados
                if a_insertar:
                    cols = self.columns + ["valido_desde", "es_vigente", "hash_atributos"]
                    placeholders = ", ".join(["%s"] * len(cols))
                    cur.executemany(
                        f"""INSERT INTO {self.target} ({", ".join(cols)})
                                 VALUES ({placeholders})""",  # noqa: S608
                        [
                            tuple(r.get(c) for c in self.columns)
                            + (self.vigencia, True, r["hash_atributos"])
                            for r in a_insertar
                        ],
                    )
                afectados = len(a_insertar)

            conn.commit()

        logger.info(
            "%s: %s nuevos, %s versionados, %s sin cambio",
            self.target,
            len(nuevos),
            len(cambiados),
            len(registros) - afectados,
        )
        return afectados
