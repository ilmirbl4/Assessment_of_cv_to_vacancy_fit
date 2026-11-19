"""Адаптер USER-bge-m3 для поиска по импортированным векторам."""

from array import array
from collections.abc import Sequence
from typing import cast

from app.config import Settings
from app.domain.models import Embedding
from app.ml.artifacts import identity
from app.ml.inference import FloatArray, Inference


class SentenceTransformersBiEncoder:
    """Энкодер, совместимый с векторами вакансий из fill_bd."""

    def __init__(self, path: str, threads: int, settings: Settings) -> None:
        """Load and validate configured encoder."""
        inference = dict(
            max_tokens=settings.ml_encoder_max_tokens,
            overlap_tokens=settings.ml_encoder_overlap,
            batch_size=settings.ml_encoder_batch_size,
        )
        self.version, self.config = identity("encoder", path, inference, settings.ml_manifest_path)
        self.dim = settings.ml_embedding_dim
        self.model = Inference("encoder", path, threads, inference, self.dim)

    def encode(self, texts: Sequence[str]) -> list[Embedding]:
        """Кодирует тексты в порядке входной последовательности."""
        predictions = self.model.predict([{"model_text": text} for text in texts])
        return [array("f", cast(FloatArray, vector)) for vector, _ in predictions]
