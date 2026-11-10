"""Сборка ML-компонентов по настройкам."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.domain.models import ModelSpec, RequirementType
from app.ml.baseline import BaselineRequirementExtractor, HashingBiEncoder, LexicalPairScorer
from app.ml.fragments import RuleResumeSegmenter
from app.ml.interfaces import BiEncoder, PairScorer, RequirementExtractor, ResumeSegmenter

TYPE_PREFIX = {
    RequirementType.HARD_SKILL: "Навык",
    RequirementType.SOFT_SKILL: "Качество",
    RequirementType.EXPERIENCE: "Опыт",
    RequirementType.EDUCATION: "Образование",
    RequirementType.CERTIFICATE: "Документ",
    RequirementType.LANGUAGE: "Язык",
}
PARTIAL_CREDIT = 0.5


@dataclass(frozen=True, slots=True)
class MlComponents:
    """Набор ML-компонентов."""

    extractor: RequirementExtractor
    segmenter: ResumeSegmenter
    bi_encoder: BiEncoder
    scorer: PairScorer

    @property
    def vacancy_model_version(self) -> str:
        """Версия обработки вакансии (ТЗ п. 4.6.4)."""
        return f"{self.extractor.version}+{self.bi_encoder.version}"

    @property
    def resume_model_version(self) -> str:
        """Версия обработки резюме."""
        return f"{self.segmenter.version}+{self.bi_encoder.version}"


def build_ml(settings: Settings) -> MlComponents:
    """Выбирает базовые реализации или настоящие модели по ``ML_BI_ENCODER_PATH`` и ``ML_CROSS_ENCODER_PATH``."""
    scorer: PairScorer = LexicalPairScorer()
    if settings.ml_cross_encoder_path:
        from app.ml.cross_encoder import SentenceTransformersPairScorer

        scorer = SentenceTransformersPairScorer(
            settings.ml_cross_encoder_path, settings.ml_model_version, settings.ml_batch_size
        )
    bi_encoder: BiEncoder = HashingBiEncoder()
    if settings.ml_bi_encoder_path:
        from app.ml.bi_encoder import SentenceTransformersBiEncoder

        bi_encoder = SentenceTransformersBiEncoder(
            settings.ml_bi_encoder_path,
            settings.ml_bi_encoder_version,
            settings.ml_bi_encoder_max_seq_length,
            settings.ml_batch_size,
            settings.ml_torch_threads,
        )
    return MlComponents(
        extractor=BaselineRequirementExtractor(),
        segmenter=RuleResumeSegmenter(),
        bi_encoder=bi_encoder,
        scorer=scorer,
    )


def model_specs(ml: MlComponents, settings: Settings) -> list[ModelSpec]:
    """Спецификации моделей для реестра в порядке ``ner``, ``bi_encoder``, ``cross_encoder``."""
    bi_real = bool(settings.ml_bi_encoder_path)
    bi_name = Path(settings.ml_bi_encoder_path).name if bi_real else ml.bi_encoder.version
    ce_real = bool(settings.ml_cross_encoder_path)
    return [
        ModelSpec("ner", ml.extractor.version, "1", f"builtin:{ml.extractor.version}", None, {}),
        ModelSpec(
            "bi_encoder",
            bi_name,
            (settings.ml_bi_encoder_version or ml.bi_encoder.version) if bi_real else "1",
            settings.ml_bi_encoder_path if bi_real else f"builtin:{ml.bi_encoder.version}",
            ml.bi_encoder.dim,
            {"max_seq_length": settings.ml_bi_encoder_max_seq_length} if bi_real else {},
        ),
        ModelSpec(
            "cross_encoder",
            ml.scorer.version if not ce_real else Path(settings.ml_cross_encoder_path).name,
            (settings.ml_model_version or ml.scorer.version) if ce_real else "1",
            settings.ml_cross_encoder_path if ce_real else f"builtin:{ml.scorer.version}",
            None,
            {
                "covered_threshold": settings.ml_covered_threshold,
                "partial_threshold": settings.ml_partial_threshold,
                "partial_credit": PARTIAL_CREDIT,
                "type_weights": {},
                "type_prefix": {t.value: prefix for t, prefix in TYPE_PREFIX.items()},
            },
        ),
    ]
