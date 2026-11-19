"""Адаптер настоящего кросс-энкодера (необязательная зависимость ``sentence-transformers``)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from app.ml.artifacts import identity


class SentenceTransformersPairScorer:
    """Оценивает пары локальным кросс-энкодером без обращения к сети."""

    def __init__(self, path: str, manifest_path: str, batch_size: int) -> None:
        """Загружает модель из локального каталога.

        Raises:
            RuntimeError: пакет ``sentence-transformers`` не установлен.
        """
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "Задан ML_CROSS_ENCODER_PATH, но пакет sentence-transformers не установлен. "
                "Выполните python -m pip install -r requirements.txt."
            ) from exc
        from torch import nn

        self._model: Any = CrossEncoder(path, local_files_only=True, device="cpu", activation_fn=nn.Identity())
        if self._model.num_labels != 1:
            raise ValueError("Кросс-энкодер должен возвращать один логит")
        self.version, self.config = identity("cross_encoder", path, {}, manifest_path)
        self._batch_size = batch_size

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        """Логиты модели переводятся в 0..1 сигмоидой; пары идут пачками."""
        if not pairs:
            return []
        from torch import nn

        logits = self._model.predict(
            [list(p) for p in pairs], batch_size=self._batch_size, activation_fn=nn.Identity(), show_progress_bar=False
        )
        return [sigmoid(float(x)) for x in logits]


def sigmoid(value: float) -> float:
    """Apply exactly one stable sigmoid to a finite raw logit."""
    if not math.isfinite(value):
        raise ValueError("Кросс-энкодер вернул нечисловой логит")
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1.0 + exp)
