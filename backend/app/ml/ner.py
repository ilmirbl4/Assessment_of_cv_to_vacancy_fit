"""Адаптер дообученного rubert-mini-frida для требований и обязанностей."""

from app.config import Settings
from app.domain.models import NormalizedVacancy, RequirementType, VacancyRequirement
from app.ml.artifacts import identity
from app.ml.inference import Inference
from app.ml.normalization import prepare_text


class FridaRequirementExtractor:
    """Выделяет требования со смещениями внутри нормализованного поля."""

    def __init__(self, path: str, threads: int, settings: Settings) -> None:
        """Load a BIO export; label order comes from config.json."""
        inference = dict(
            max_tokens=settings.ml_ner_max_tokens,
            overlap_tokens=settings.ml_ner_overlap,
            batch_size=settings.ml_ner_batch_size,
        )
        self.version, self.config = identity("ner", path, inference, settings.ml_manifest_path)
        self.model = Inference("ner", path, threads, inference)

    def extract(self, vacancy: NormalizedVacancy) -> list[VacancyRequirement]:
        """Возвращает требования и обязанности, выделенные из текста вакансии."""
        text, bodies, sections = prepare_text(vacancy.raw.get("requirements"), vacancy.raw.get("duty"))
        if not text:
            return []
        row = {"model_text": text, "fields": {**bodies, "source_fields": sections}}
        ((entities, _),) = self.model.predict([row])
        if not isinstance(entities, list):
            raise RuntimeError("NER вернула результат неожиданного типа")
        return [
            VacancyRequirement(
                RequirementType(e["requirement_type"]),
                e["text"],
                e["source_field"],
                e["span_start"],
                e["span_end"],
                e["is_preferred"],
            )
            for e in entities
        ]
