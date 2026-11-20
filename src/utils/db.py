"""Acceso a PostgreSQL con psycopg 3."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from pathlib import Path

import psycopg

from src.config.settings import DBSettings


@contextmanager
def connection():
    with psycopg.connect(DBSettings.from_env().dsn) as conn:
        yield conn


def file_hash(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def attribute_hash(record: dict, columns: list[str]) -> str:
    """Hash de los atributos versionados de una dimensión (detección de cambios)."""
    payload = "|".join(str(record.get(c, "")) for c in columns)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()
