"""Mandatory offline models and a bounded shared inference executor."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
from typing import Any

from app.config import Settings
from app.domain.models import ModelSpec
from app.ml.artifacts import fingerprint
from app.ml.fragments import RuleResumeSegmenter
from app.ml.interfaces import BiEncoder, PairScorer, RequirementExtractor, ResumeSegmenter
from app.ml.normalization import VERSION as NORMALIZATION_VERSION
from app.ml.profile import PROFILE

CURRENT_PROCESSING = {
    "content_hash": "sha256-utf8-json-array-v1",
    "mapping": "fill-bd-mapping-v1",
    "normalization": NORMALIZATION_VERSION,
}


@dataclass(slots=True)
class MlComponents:
    """Shared models; only one CPU inference runs at a time."""

    extractor: RequirementExtractor
    segmenter: ResumeSegmenter
    bi_encoder: BiEncoder
    scorer: PairScorer
    max_pending: int = 12
    _pending: int = 0
    _executor: ThreadPoolExecutor = field(default_factory=lambda: ThreadPoolExecutor(max_workers=1))

    @property
    def vacancy_model_version(self) -> str:
        """Preserve the imported pipeline when its contracts are identical."""
        if (
            self.extractor.version == PROFILE["profiles"]["ner"]["version"]
            and self.bi_encoder.version == PROFILE["profiles"]["encoder"]["version"]
            and PROFILE["processing"] == CURRENT_PROCESSING
        ):
            return str(PROFILE["model_version"])
        return fingerprint([self.extractor.version, self.bi_encoder.version, PROFILE["processing"]])

    @property
    def resume_model_version(self) -> str:
        """Identity of resume preparation: segmentation and the embedding model only."""
        return fingerprint([self.segmenter.version, self.bi_encoder.version])

    async def run(self, fn: Callable[..., Any], *args: Any) -> Any:
        """Bound the queue and keep the slot until a cancelled thread actually completes."""
        if self._pending >= self.max_pending:
            from fastapi import HTTPException

            raise HTTPException(503, "Очередь обработки заполнена. Повторите запрос позже.")
        self._pending += 1
        future = asyncio.get_running_loop().run_in_executor(self._executor, partial(fn, *args))
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            await asyncio.shield(future)
            raise
        finally:
            self._pending -= 1


def build_ml(settings: Settings) -> MlComponents:
    """Load all mandatory artifacts; never fall back to lexical scores."""
    from app.ml.bi_encoder import SentenceTransformersBiEncoder
    from app.ml.cross_encoder import SentenceTransformersPairScorer
    from app.ml.ner import FridaRequirementExtractor

    return MlComponents(
        FridaRequirementExtractor(settings.ml_ner_path, settings.ml_torch_threads, settings),
        RuleResumeSegmenter(),
        SentenceTransformersBiEncoder(settings.ml_bi_encoder_path, settings.ml_torch_threads, settings),
        SentenceTransformersPairScorer(
            settings.ml_cross_encoder_path, settings.ml_manifest_path, settings.ml_batch_size
        ),
        settings.ml_max_pending,
    )


def pipeline_id(ml: MlComponents, settings: Settings) -> str:
    """Coverage cache includes selection, extraction, aggregation and thresholds."""
    return fingerprint(
        [
            ml.resume_model_version,
            ml.vacancy_model_version,
            ml.scorer.version,
            settings.match_phrases_per_requirement,
            settings.ml_partial_threshold,
            settings.ml_covered_threshold,
            "semantic-topk-v1",
            "coverage-v1",
        ]
    )


def model_specs(ml: MlComponents, settings: Settings) -> list[ModelSpec]:
    """Mathematical model identity is separate from thresholds and deployment paths."""
    return [
        ModelSpec(
            "ner",
            "rubert-mini-frida-ner",
            ml.extractor.version,
            settings.ml_ner_path,
            None,
            getattr(ml.extractor, "config", {}),
        ),
        ModelSpec(
            "bi_encoder",
            "deepvk/USER-bge-m3",
            ml.bi_encoder.version,
            settings.ml_bi_encoder_path,
            ml.bi_encoder.dim,
            getattr(ml.bi_encoder, "config", {}),
        ),
        ModelSpec(
            "cross_encoder",
            "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
            ml.scorer.version,
            settings.ml_cross_encoder_path,
            None,
            getattr(ml.scorer, "config", {}),
        ),
    ]
