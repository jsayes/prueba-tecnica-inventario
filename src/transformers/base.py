"""Contrato de transformación: componible y sin efectos secundarios."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Iterator


class BaseTransformer(ABC):
    @abstractmethod
    def transform(self, records: Iterable[dict]) -> Iterator[dict]:
        ...


class Chain(BaseTransformer):
    """Encadena transformers en orden."""

    def __init__(self, *transformers: BaseTransformer) -> None:
        self.transformers = transformers

    def transform(self, records: Iterable[dict]) -> Iterator[dict]:
        for t in self.transformers:
            records = t.transform(records)
        yield from records
