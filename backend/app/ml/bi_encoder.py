"""Адаптер настоящего би-энкодера (необязательная зависимость ``sentence-transformers``)."""

from __future__ import annotations

from array import array
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.domain.models import Embedding


class SentenceTransformersBiEncoder:
    """Кодирует тексты локальной моделью sentence-transformers без обращения к сети."""

    def __init__(self, path: str, version: str, max_seq_length: int, batch_size: int, torch_threads: int) -> None:
        """Загружает модель из локального каталога.

        Raises:
            RuntimeError: пакет ``sentence-transformers`` не установлен.
        """
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Задан ML_BI_ENCODER_PATH, но пакет sentence-transformers не установлен (uv sync --extra ml)"
            ) from exc
        torch.set_num_threads(torch_threads)
        self._model: Any = SentenceTransformer(path, device="cpu", local_files_only=True)
        self._model.max_seq_length = max_seq_length
        self.version = version or Path(path).name
        # в sentence-transformers 6 метод переименован; старое имя даёт FutureWarning
        get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        self.dim: int = get_dim() or 0
        self._batch_size = batch_size

    def encode(self, texts: Sequence[str]) -> list[Embedding]:
        """L2-нормированные векторы в порядке ``texts``."""
        if not texts:
            return []
        matrix = self._model.encode(
            list(texts), batch_size=self._batch_size, normalize_embeddings=True, convert_to_numpy=True
        )
        return [array("f", row.tolist()) for row in matrix]
