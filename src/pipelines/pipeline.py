"""Composición y ejecución de un flujo. IMPLEMENTADO.

El pipeline no conoce el formato del origen ni el motor de destino: recibe los
componentes ya construidos. Se encarga de la secuencia, del registro de la
ejecución en el schema etl y del reporte de métricas.
"""
from __future__ import annotations

from typing import Iterable

from src.extractors.base import BaseExtractor
from src.loaders.base import BaseLoader
from src.quality.rules import Validador
from src.transformers.base import BaseTransformer
from src.utils.logger import get_logger
from src.utils.run_tracker import cerrar_ejecucion, iniciar_ejecucion, registrar_rechazos

logger = get_logger(__name__)


class Pipeline:
    def __init__(
        self,
        nombre: str,
        extractor: BaseExtractor,
        transformer: BaseTransformer,
        loader: BaseLoader,
        validador: Validador | None = None,
        parametros: dict | None = None,
    ) -> None:
        self.nombre = nombre
        self.extractor = extractor
        self.transformer = transformer
        self.loader = loader
        self.validador = validador
        self.parametros = parametros or {}

    def run(self) -> dict:
        id_ejecucion = iniciar_ejecucion(self.nombre, {**self.parametros, "origen": self.extractor.origen})
        metricas = {"leidas": 0, "cargadas": 0, "rechazadas": 0}
        try:
            crudos = list(self.extractor.extract())
            metricas["leidas"] = len(crudos)

            transformados: Iterable[dict] = self.transformer.transform(crudos)

            if self.validador:
                resultado = self.validador.run(transformados)
                transformados = resultado.validos
                metricas["rechazadas"] = len(resultado.rechazados)
                registrar_rechazos(id_ejecucion, self.nombre, resultado.rechazados)
                logger.info("[%s] calidad %s", self.nombre, resultado.resumen)

            metricas["cargadas"] = self.loader.load(transformados)
            cerrar_ejecucion(id_ejecucion, "EXITO", metricas)
            logger.info("[%s] EXITO %s", self.nombre, metricas)
            return metricas
        except Exception as exc:
            cerrar_ejecucion(id_ejecucion, "FALLO", metricas, str(exc))
            logger.exception("[%s] FALLO", self.nombre)
            raise
