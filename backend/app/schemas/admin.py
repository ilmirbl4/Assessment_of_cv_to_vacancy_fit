"""Administrative API response contracts, including unavailable metrics."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CollectionRun(BaseModel):
    """Запуск сбора в журнале."""

    id: str
    started_at: datetime
    finished_at: datetime | None
    status: Literal["running", "success", "partial", "failed"]
    new_count: int
    updated_count: int
    deactivated_count: int
    error_count: int
    error_message: str | None = None


class CollectionDashboard(BaseModel):
    """Дашборд сбора данных."""

    active_vacancies_total: int
    is_running: bool
    runs: list[CollectionRun]
    bootstrap: dict[str, Any]


class SpeedDay(BaseModel):
    """Агрегат скорости подбора за сутки."""

    date: date
    avg_ms: float
    p95_ms: float
    count: int


class SpeedDashboard(BaseModel):
    """Дашборд скорости подбора."""

    days: list[SpeedDay]


class DistributionBin(BaseModel):
    """Корзина распределения признака."""

    bin: str
    share: float


class Availability(BaseModel):
    """Доступность метрики и причина её отсутствия."""

    status: Literal["ready", "insufficient_data", "reference_missing", "reference_incompatible"]
    reason: str | None = None
    reference_size: int = 0
    current_size: int = 0


class DriftIndicator(Availability):
    """PSI-индикатор дрейфа признака."""

    key: str
    name: str
    entity: Literal["vacancies", "resumes"]
    bins_label: str
    psi: float | None
    reference: list[DistributionBin]
    current: list[DistributionBin]


class Period(BaseModel):
    """Период наблюдений."""

    from_: str = Field(alias="from")
    to: str


class AucPeriod(Period):
    """Период с ROC-AUC состязательной валидации."""

    roc_auc: float


class Importance(BaseModel):
    """Важность признака классификатора."""

    name: str
    importance: float


class Adversarial(Availability):
    """Результат состязательной валидации."""

    roc_auc: float | None
    roc_auc_threshold: float
    periods: list[AucPeriod]
    top_features: list[Importance]
    train_size: int = 0
    test_size: int = 0
    method: str | None = None


class ScoreDrift(Availability):
    """Дрейф распределения оценок кросс-энкодера."""

    statistic: float | None
    p_value: float | None
    alpha: float
    reference: list[DistributionBin]
    current: list[DistributionBin]


class FavoriteRateDay(BaseModel):
    """Доля подборов с избранным за сутки."""

    date: date
    runs: int
    runs_with_favorite: int
    share: float | None


class FavoriteRate(Availability):
    """Дрейф пользовательского отклика."""

    reference_share: float | None
    max_drop: float
    days: list[FavoriteRateDay]


class DriftDashboard(BaseModel):
    """Полный дашборд дрейфа данных."""

    reference_period: Period
    current_period: Period
    reference_id: str
    pipeline_id: str
    reference_size: int
    current_size: int
    batch_id: str | None
    checked_at: datetime
    psi_threshold: float
    indicators: list[DriftIndicator]
    adversarial: Adversarial
    model_scores: ScoreDrift
    favorite_rate: FavoriteRate
