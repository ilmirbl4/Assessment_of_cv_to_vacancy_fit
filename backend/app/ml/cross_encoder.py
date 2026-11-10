"""Адаптер настоящего кросс-энкодера (необязательная зависимость ``sentence-transformers``)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any


class SentenceTransformersPairScorer:
    """Оценивает пары локальным кросс-энкодером без обращения к сети."""

    def __init__(self, path: str, version: str, batch_size: int) -> None:
        """Загружает модель из локального каталога.

        Raises:
            RuntimeError: пакет ``sentence-transformers`` не установлен.
        """
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "Задан ML_CROSS_ENCODER_PATH, но пакет sentence-transformers не установлен (uv sync --extra ml)"
            ) from exc
        self._model: Any = CrossEncoder(path, local_files_only=True)
        self.version = version or Path(path).name
        self._batch_size = batch_size

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        """Логиты модели переводятся в 0..1 сигмоидой; пары идут пачками."""
        if not pairs:
            return []
        logits = self._model.predict([list(p) for p in pairs], batch_size=self._batch_size)
        return [1.0 / (1.0 + math.exp(-float(x))) for x in logits]
