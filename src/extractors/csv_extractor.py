"""Extractor de CSV. Implementado como referencia."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from src.extractors.base import BaseExtractor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CSVExtractor(BaseExtractor):
    def __init__(self, path: str | Path, delimiter: str = ",") -> None:
        self.path = Path(path)
        self.delimiter = delimiter

    @property
    def origen(self) -> str:
        return str(self.path)

    def extract(self) -> Iterator[dict]:
        if not self.path.exists():
            raise FileNotFoundError(f"No existe el archivo de origen: {self.path}")
        logger.info("Extrayendo %s", self.path)
        with open(self.path, newline="", encoding="utf-8") as fh:
            for i, row in enumerate(csv.DictReader(fh, delimiter=self.delimiter), start=2):
                row["_linea_archivo"] = i
                row["_archivo_origen"] = self.path.name
                yield row


def build_extractor(kind: str, **kwargs) -> BaseExtractor:
    """Fábrica de extractores.

    TODO (candidato): si agregas una fuente que no sea CSV (API, base de datos,
    parquet), regístrala aquí sin tocar los pipelines.
    """
    registry = {"csv": CSVExtractor}
    if kind not in registry:
        raise ValueError(f"Extractor no soportado: {kind}")
    return registry[kind](**kwargs)
