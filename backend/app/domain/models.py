"""Сущности предметной области (раздел 5.2 инструкции)."""

from __future__ import annotations

from array import array
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

# L2-нормированный вектор ``array("f")``: компактно и без numpy в домене.
Embedding = array[float]


class Role(StrEnum):
    """Роль пользователя."""

    SEEKER = "seeker"
    ADMIN = "admin"


class RequirementType(StrEnum):
    """Тип требования вакансии."""

    HARD_SKILL = "HARD_SKILL"
    SOFT_SKILL = "SOFT_SKILL"
    EXPERIENCE = "EXPERIENCE"
    EDUCATION = "EDUCATION"
    CERTIFICATE = "CERTIFICATE"
    LANGUAGE = "LANGUAGE"


class TokenPurpose(StrEnum):
    """Назначение одноразового токена."""

    CONFIRM_EMAIL = "confirm_email"
    RESET = "reset_password"


class ResumeStatus(StrEnum):
    """Статус обработки резюме."""

    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class RequirementStatus(StrEnum):
    """Статус покрытия требования резюме."""

    COVERED = "covered"
    PARTIALLY_COVERED = "partially_covered"
    NOT_COVERED = "not_covered"


class RunMode(StrEnum):
    """Режим сбора вакансий."""

    INCREMENTAL = "incremental"
    FULL = "full"


class RunStatus(StrEnum):
    """Статус запуска сбора."""

    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class User:
    """Пользователь системы."""

    id: str
    email: str
    password_hash: str
    role: Role
    email_confirmed_at: datetime | None
    consent_version: str | None
    consent_accepted_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Session:
    """Сессия входа (хранится хеш токена)."""

    token_hash: str
    user_id: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AuthToken:
    """Одноразовый токен подтверждения адреса или сброса пароля."""

    token_hash: str
    user_id: str
    purpose: TokenPurpose
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ResumeFragment:
    """Фрагмент резюме со смещениями в тексте."""

    ord: int
    text: str
    span_start: int
    span_end: int


@dataclass(frozen=True, slots=True)
class Resume:
    """Резюме пользователя: хранится только извлечённый текст и результаты обработки."""

    id: str
    user_id: str
    file_name: str
    file_type: str
    uploaded_at: datetime
    status: ResumeStatus
    error_message: str | None
    text: str
    fragments: tuple[ResumeFragment, ...] = ()
    embedding: Embedding | None = None
    model_version: str | None = None
    processed_at: datetime | None = None

    @property
    def phrases(self) -> tuple[str, ...]:
        """Тексты фрагментов по порядку."""
        return tuple(f.text for f in self.fragments)


@dataclass(frozen=True, slots=True)
class SourceField:
    """Поле страницы вакансии: подпись и значение."""

    label: str
    value: str


@dataclass(frozen=True, slots=True)
class VacancyRequirement:
    """Требование вакансии: дословный срез нормализованного поля."""

    type: RequirementType
    text: str
    source_field: str  # "requirements" | "duties"
    span_start: int
    span_end: int
    is_preferred: bool = False


@dataclass(frozen=True, slots=True)
class Employer:
    """Работодатель (коды источника; поля могут отсутствовать)."""

    source_code: str
    inn: str | None = None
    ogrn: str | None = None
    kpp: str | None = None
    site_url: str | None = None


@dataclass(frozen=True, slots=True)
class Vacancy:
    """Вакансия."""

    id: str
    title: str
    salary_from: int | None
    salary_to: int | None
    employer_name: str
    published_at: date
    region_code: str | None
    region_name: str
    employment_code: str | None
    schedule_code: str | None
    experience_code: str | None
    professional_area: str | None
    source_url: str
    source_fields: tuple[SourceField, ...]
    requirements: tuple[VacancyRequirement, ...]
    embedding: Embedding | None
    model_version: str
    date_modify: datetime
    is_active: bool
    first_seen_at: datetime
    updated_at: datetime
    deactivated_at: datetime | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)
    requirements_section: str = ""
    duties_section: str = ""
    qualification: str | None = None
    education: str | None = None
    experience_years: int | None = None
    employer: Employer | None = None
    content_hash: bytes = b""


@dataclass(frozen=True, slots=True)
class VacancyCandidate:
    """Лёгкое представление вакансии для быстрого отбора."""

    id: str
    published_at: date
    score: float


@dataclass(frozen=True, slots=True)
class UpsertResult:
    """Итог пакетной записи вакансий."""

    new: int
    updated: int
    unchanged: int
    failed_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IngestState:
    """Состояние вакансии в хранилище для пропуска неизменённых."""

    date_modify: datetime
    content_hash: bytes
    is_active: bool
    analysis_fresh: bool  # есть вектор активной модели по этому тексту и совпала model_version


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Описание ML-модели для реестра."""

    kind: str  # bi_encoder | cross_encoder | ner
    name: str
    version: str
    artifact_uri: str
    embedding_dim: int | None
    config: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Favorite:
    """Запись избранного."""

    user_id: str
    vacancy_id: str
    added_at: datetime


@dataclass(frozen=True, slots=True)
class MatchFilters:
    """Фильтры подбора."""

    region_code: str | None = None
    min_salary: int | None = None
    only_with_salary: bool = False
    employment_type: str | None = None
    schedule: str | None = None
    experience: str | None = None


@dataclass(frozen=True, slots=True)
class RequirementVerdict:
    """Вердикт по одному требованию."""

    number: int
    text: str
    status: RequirementStatus
    resume_quote: str | None
    requirement: VacancyRequirement | None = None
    score: float = 0.0
    fragment_ord: int | None = None


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Результат сопоставления резюме с одной вакансией."""

    vacancy_id: str
    match_percent: int
    verdicts: tuple[RequirementVerdict, ...]
    coverage_score: float = 0.0
    retrieval_score: float = 0.0


@dataclass(frozen=True, slots=True)
class MatchRun:
    """Текущий подбор пользователя."""

    id: str
    user_id: str
    resume_id: str
    created_at: datetime
    filters: MatchFilters
    results: tuple[MatchResult, ...]
    candidates_k: int = 300


@dataclass(frozen=True, slots=True)
class CollectionRun:
    """Запуск сбора вакансий."""

    id: str
    mode: RunMode
    started_at: datetime
    finished_at: datetime | None
    status: RunStatus
    snapshot_at: datetime
    modified_from: datetime | None = None
    new_count: int = 0
    updated_count: int = 0
    deactivated_count: int = 0
    error_count: int = 0
    complete: bool = False
    error_message: str | None = None
    unchanged_count: int = 0
    pages_fetched: int = 0
    received: int = 0


@dataclass(frozen=True, slots=True)
class MatchingEvent:
    """Анонимное событие подбора (длительность)."""

    run_id: str
    at: datetime
    duration_ms: int
    results_count: int


@dataclass(frozen=True, slots=True)
class FavoriteFromRunEvent:
    """Анонимное событие «добавил в избранное из подбора»."""

    run_id: str
    at: datetime


@dataclass(frozen=True, slots=True)
class NormalizedVacancy:
    """Вакансия после нормализации сырого JSON источника, до выделения требований."""

    id: str
    title: str
    salary_from: int | None
    salary_to: int | None
    employer_name: str
    published_at: date
    region_code: str | None
    region_name: str
    employment_code: str | None
    schedule_code: str | None
    experience_code: str | None
    professional_area: str | None
    source_url: str
    source_fields: tuple[SourceField, ...]
    requirements: str
    duties: str
    skills: tuple[str, ...]
    date_modify: datetime
    raw: Mapping[str, Any] = field(default_factory=dict)
    qualification: str | None = None
    education: str | None = None
    experience_years: int | None = None
    employer: Employer | None = None
    content_hash: bytes = b""
