"""Contrato de extracción: leer de una fuente, nada más."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self) -> Iterator[dict]:
        """Devuelve registros crudos, sin transformar."""

    @property
    def origen(self) -> str:
        """Identificador del origen leído (ruta, endpoint, tabla)."""
        return type(self).__name__
