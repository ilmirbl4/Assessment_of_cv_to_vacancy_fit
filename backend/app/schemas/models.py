"""Схемы API. Модели ответов не имеют значений по умолчанию: поля всегда присутствуют."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, StrictBool, StrictInt, StringConstraints

from app.domain import models as dm

MAX_SALARY = 10_000_000


def iso(moment: datetime, timezone: str) -> str:
    """Момент времени в ISO 8601 с точностью до секунды в заданном поясе."""
    return moment.astimezone(ZoneInfo(timezone)).replace(microsecond=0).isoformat()


# ---------- ответы ----------


class Empty(BaseModel):
    """Пустой объект успешного ответа."""


class HealthStatus(BaseModel):
    """Состояние сервиса."""

    status: str


class ErrorInfo(BaseModel):
    """Описание ошибки."""

    code: str
    message: str
    fields: dict[str, str] | None = None


class ApiErrorBody(BaseModel):
    """Тело ответа с ошибкой."""

    error: ErrorInfo


class User(BaseModel):
    """Пользователь."""

    id: str
    email: str
    role: Literal["seeker", "admin"]


class Option(BaseModel):
    """Элемент справочника."""

    code: str
    name: str


class Dictionaries(BaseModel):
    """Справочники фильтров."""

    regions: list[Option]
    employment_types: list[Option]
    schedules: list[Option]
    experience: list[Option]


class Consent(BaseModel):
    """Согласие на обработку ПДн."""

    version: str
    text: str
    published_at: str


class Resume(BaseModel):
    """Резюме."""

    file_name: str
    uploaded_at: str
    status: Literal["processing", "ready", "failed"]
    error_message: str | None


class MatchFilters(BaseModel):
    """Фильтры подбора в ответе (все поля обязательны)."""

    region_code: str | None
    min_salary: int | None
    only_with_salary: bool
    employment_type: str | None
    schedule: str | None
    experience: str | None


class VacancyCard(BaseModel):
    """Карточка вакансии в подборе."""

    id: str
    title: str
    salary_from: int | None
    salary_to: int | None
    employer_name: str
    published_at: str
    match_percent: int


class FavoriteVacancy(BaseModel):
    """Карточка вакансии в избранном (без степени соответствия)."""

    id: str
    title: str
    salary_from: int | None
    salary_to: int | None
    employer_name: str
    published_at: str


class MatchPage(BaseModel):
    """Страница результатов подбора."""

    run_id: str
    created_at: str
    filters: MatchFilters
    total: int
    page: int
    page_size: Literal[10]
    total_pages: int
    items: list[VacancyCard]


class Requirement(BaseModel):
    """Требование вакансии и вердикт по нему."""

    number: int
    text: str
    status: Literal["covered", "partially_covered", "not_covered"]
    resume_quote: str | None


class SourceField(BaseModel):
    """Поле страницы вакансии."""

    label: str
    value: str


class VacancyDetail(BaseModel):
    """Страница вакансии."""

    id: str
    title: str
    salary_from: int | None
    salary_to: int | None
    employer_name: str
    published_at: str
    match_percent: int | None
    region_name: str
    source_url: str
    is_active: bool
    is_favorite: bool
    source_fields: list[SourceField]
    requirements: list[Requirement]


class FavoriteItem(BaseModel):
    """Элемент избранного."""

    vacancy: FavoriteVacancy
    is_active: bool
    added_at: str


# ---------- запросы ----------

Email = Annotated[str, StringConstraints(strip_whitespace=True, max_length=254)]


class RegisterRequest(BaseModel):
    """Регистрация."""

    email: Email
    password: Annotated[str, StringConstraints(max_length=128)]
    consent_accepted: StrictBool
    consent_version: str


class LoginRequest(BaseModel):
    """Вход."""

    email: str
    password: str


class TokenRequest(BaseModel):
    """Токен из письма."""

    token: str


class EmailRequest(BaseModel):
    """Адрес электронной почты."""

    email: str


class PasswordResetConfirmRequest(BaseModel):
    """Подтверждение сброса пароля."""

    token: str
    new_password: str


class MatchFiltersRequest(BaseModel):
    """Фильтры подбора во входе (все поля необязательны)."""

    region_code: str | None = None
    min_salary: Annotated[StrictInt, Field(ge=0, le=MAX_SALARY)] | None = None
    only_with_salary: StrictBool = False
    employment_type: str | None = None
    schedule: str | None = None
    experience: str | None = None


class MatchRunRequest(BaseModel):
    """Запуск подбора."""

    filters: MatchFiltersRequest


class FavoriteRequest(BaseModel):
    """Добавление в избранное."""

    vacancy_id: Annotated[str, StringConstraints(max_length=64)]


# ---------- преобразования ----------


def user_out(user: dm.User) -> User:
    """Доменный пользователь → схема."""
    return User(id=user.id, email=user.email, role="admin" if user.role == dm.Role.ADMIN else "seeker")


def date_str(value: date) -> str:
    """Дата публикации ``YYYY-MM-DD``."""
    return value.isoformat()


RESUME_STATUS: dict[dm.ResumeStatus, Literal["processing", "ready", "failed"]] = {
    dm.ResumeStatus.PROCESSING: "processing",
    dm.ResumeStatus.READY: "ready",
    dm.ResumeStatus.FAILED: "failed",
}
REQUIREMENT_STATUS: dict[dm.RequirementStatus, Literal["covered", "partially_covered", "not_covered"]] = {
    dm.RequirementStatus.COVERED: "covered",
    dm.RequirementStatus.PARTIALLY_COVERED: "partially_covered",
    dm.RequirementStatus.NOT_COVERED: "not_covered",
}


def resume_out(resume: dm.Resume, timezone: str) -> Resume:
    """Доменное резюме → схема."""
    return Resume(
        file_name=resume.file_name,
        uploaded_at=iso(resume.uploaded_at, timezone),
        status=RESUME_STATUS[resume.status],
        error_message=resume.error_message if resume.status == dm.ResumeStatus.FAILED else None,
    )


def filters_out(filters: dm.MatchFilters) -> MatchFilters:
    """Доменные фильтры → схема ответа."""
    return MatchFilters(
        region_code=filters.region_code,
        min_salary=filters.min_salary,
        only_with_salary=filters.only_with_salary,
        employment_type=filters.employment_type,
        schedule=filters.schedule,
        experience=filters.experience,
    )


def card_out(vacancy: dm.Vacancy, percent: int) -> VacancyCard:
    """Карточка вакансии подбора."""
    return VacancyCard(
        id=vacancy.id,
        title=vacancy.title,
        salary_from=vacancy.salary_from,
        salary_to=vacancy.salary_to,
        employer_name=vacancy.employer_name,
        published_at=date_str(vacancy.published_at),
        match_percent=percent,
    )


def favorite_vacancy_out(vacancy: dm.Vacancy) -> FavoriteVacancy:
    """Карточка вакансии избранного."""
    return FavoriteVacancy(
        id=vacancy.id,
        title=vacancy.title,
        salary_from=vacancy.salary_from,
        salary_to=vacancy.salary_to,
        employer_name=vacancy.employer_name,
        published_at=date_str(vacancy.published_at),
    )
