"""Contrato de carga."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable


class BaseLoader(ABC):
    def __init__(self, target: str, natural_key: list[str]) -> None:
        self.target = target
        self.natural_key = natural_key

    @abstractmethod
    def load(self, records: Iterable[dict]) -> int:
        """Carga los registros y devuelve la cantidad de filas afectadas."""
