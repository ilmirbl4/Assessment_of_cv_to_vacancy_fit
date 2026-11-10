"""Интерфейсы репозиториев (typing.Protocol). Все методы асинхронные, чтобы БД встала на место заглушек."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Protocol

from app.domain.models import (
    AuthToken,
    CollectionRun,
    Embedding,
    Favorite,
    FavoriteFromRunEvent,
    IngestState,
    MatchFilters,
    MatchingEvent,
    MatchRun,
    ModelSpec,
    Resume,
    ResumeFragment,
    Session,
    TokenPurpose,
    UpsertResult,
    User,
    Vacancy,
    VacancyCandidate,
)


class ModelRegistry(Protocol):
    """Реестр ML-моделей: активные версии компонентов."""

    async def activate(self, specs: Sequence[ModelSpec]) -> None:
        """Регистрирует модели и делает их активными (прежние активные того же вида архивируются)."""
        ...


class UserRepository(Protocol):
    """Пользователи."""

    async def get_by_id(self, user_id: str) -> User | None:
        """Возвращает пользователя по идентификатору."""
        ...

    async def get_by_email(self, email: str) -> User | None:
        """Возвращает пользователя по нормализованному адресу."""
        ...

    async def create(self, user: User) -> None:
        """Создаёт пользователя; при занятом email бросает ``AlreadyExistsError``."""
        ...

    async def update_password_hash(self, user_id: str, password_hash: str) -> None:
        """Обновляет хеш пароля."""
        ...

    async def mark_email_confirmed(self, user_id: str, at: datetime) -> None:
        """Отмечает адрес подтверждённым."""
        ...

    async def delete(self, user_id: str) -> None:
        """Удаляет пользователя."""
        ...


class SessionRepository(Protocol):
    """Сессии."""

    async def create(self, session: Session) -> None:
        """Сохраняет сессию."""
        ...

    async def get(self, token_hash: str) -> Session | None:
        """Возвращает сессию по хешу токена."""
        ...

    async def delete(self, token_hash: str) -> None:
        """Удаляет сессию."""
        ...

    async def delete_all_for_user(self, user_id: str) -> None:
        """Удаляет все сессии пользователя."""
        ...

    async def delete_expired(self, now: datetime) -> int:
        """Удаляет истёкшие сессии и возвращает их число."""
        ...


class AuthTokenRepository(Protocol):
    """Одноразовые токены."""

    async def create(self, token: AuthToken) -> None:
        """Сохраняет токен."""
        ...

    async def get_valid(self, token_hash: str, purpose: TokenPurpose, now: datetime) -> AuthToken | None:
        """Возвращает токен, если он не использован и не истёк."""
        ...

    async def mark_used(self, token_hash: str, at: datetime) -> None:
        """Помечает токен использованным."""
        ...

    async def invalidate_for_user(self, user_id: str, purpose: TokenPurpose) -> None:
        """Аннулирует все токены пользователя с данным назначением."""
        ...

    async def last_created_at(self, user_id: str, purpose: TokenPurpose) -> datetime | None:
        """Момент создания последнего токена (для паузы между письмами)."""
        ...

    async def delete_all_for_user(self, user_id: str) -> None:
        """Удаляет все токены пользователя."""
        ...


class ResumeRepository(Protocol):
    """Резюме (одно на пользователя)."""

    async def get(self, user_id: str) -> Resume | None:
        """Возвращает текущее резюме пользователя."""
        ...

    async def replace(self, resume: Resume) -> None:
        """Замещает резюме пользователя новым."""
        ...

    async def complete_processing(
        self,
        user_id: str,
        resume_id: str,
        *,
        status: str,
        error_message: str | None,
        fragments: Sequence[ResumeFragment],
        embedding: Embedding | None,
        model_version: str | None,
        processed_at: datetime,
    ) -> bool:
        """Записывает результат обработки; ``False``, если ``resume_id`` уже не текущий."""
        ...

    async def delete(self, user_id: str) -> None:
        """Удаляет резюме пользователя."""
        ...

    async def list_processing_started_before(self, moment: datetime) -> list[Resume]:
        """Резюме в обработке, загруженные раньше ``moment``."""
        ...


class VacancyRepository(Protocol):
    """Вакансии."""

    async def get(self, vacancy_id: str) -> Vacancy | None:
        """Возвращает вакансию по идентификатору."""
        ...

    async def get_many(self, ids: Collection[str]) -> dict[str, Vacancy]:
        """Возвращает найденные вакансии по списку идентификаторов."""
        ...

    async def search_candidates(self, query: Embedding, filters: MatchFilters, limit: int) -> list[VacancyCandidate]:
        """До ``limit`` активных вакансий под фильтры, ближайших к ``query``, в порядке убывания близости."""
        ...

    async def get_ingest_states(self, ids: Collection[str], model_version: str) -> dict[str, IngestState]:
        """Состояние найденных вакансий для решения о пересчёте."""
        ...

    async def upsert_batch(
        self,
        vacancies: Sequence[Vacancy],
        *,
        keep_analysis: Collection[str] = (),
        ingestion_run_id: str | None = None,
    ) -> UpsertResult:
        """Атомарно записывает пакет вакансий.

        Для id из ``keep_analysis`` требования, вектор и ``model_version`` остаются прежними.
        """
        ...

    async def deactivate_missing(self, seen_ids: Collection[str], at: datetime) -> int:
        """Деактивирует активные вакансии, которых нет в ``seen_ids``."""
        ...

    async def deactivate_ids(self, ids: Collection[str], at: datetime) -> int:
        """Деактивирует перечисленные активные вакансии, возвращает их число."""
        ...

    async def count_active(self) -> int:
        """Число активных вакансий."""
        ...


class FavoriteRepository(Protocol):
    """Избранное."""

    async def list_for_user(self, user_id: str) -> list[Favorite]:
        """Избранное пользователя по убыванию даты добавления."""
        ...

    async def add(self, favorite: Favorite) -> None:
        """Добавляет запись; при повторе бросает ``AlreadyExistsError``."""
        ...

    async def remove(self, user_id: str, vacancy_id: str) -> bool:
        """Удаляет запись; ``False``, если её не было."""
        ...

    async def exists(self, user_id: str, vacancy_id: str) -> bool:
        """Есть ли вакансия в избранном."""
        ...

    async def delete_all_for_user(self, user_id: str) -> None:
        """Удаляет всё избранное пользователя."""
        ...


class MatchRunRepository(Protocol):
    """Текущий подбор пользователя."""

    async def get_current(self, user_id: str) -> MatchRun | None:
        """Возвращает текущий подбор."""
        ...

    async def save_current(self, run: MatchRun) -> None:
        """Сохраняет подбор, заменяя прежний."""
        ...

    async def delete_for_user(self, user_id: str) -> None:
        """Удаляет подбор пользователя."""
        ...


class CollectionRunRepository(Protocol):
    """Журнал запусков сбора."""

    async def create(self, run: CollectionRun) -> None:
        """Создаёт запуск."""
        ...

    async def update(self, run: CollectionRun) -> None:
        """Обновляет запуск."""
        ...

    async def get_running(self) -> CollectionRun | None:
        """Возвращает идущий запуск."""
        ...

    async def get_last_complete(self) -> CollectionRun | None:
        """Последний запуск с ``complete = true``."""
        ...

    async def list_started_since(self, moment: datetime) -> list[CollectionRun]:
        """Запуски, начатые не раньше ``moment``."""
        ...

    async def fail_running(self, at: datetime, message: str) -> int:
        """Переводит зависшие запуски в ``failed``."""
        ...


class MetricsRepository(Protocol):
    """Сырые метрики для будущих дашбордов."""

    async def record_matching(self, event: MatchingEvent) -> None:
        """Записывает событие подбора."""
        ...

    async def record_favorite_from_run(self, event: FavoriteFromRunEvent) -> None:
        """Записывает событие «в избранное из подбора» (не более одного на подбор)."""
        ...

    async def count_favorites_from_run(self) -> int:
        """Число подборов, из которых что-то добавлено в избранное."""
        ...
