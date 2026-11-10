"""Выбор реализации хранилища по настройке ``STORAGE_BACKEND``."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.database import Database
from app.repositories.interfaces import (
    AuthTokenRepository,
    CollectionRunRepository,
    FavoriteRepository,
    MatchRunRepository,
    MetricsRepository,
    ModelRegistry,
    ResumeRepository,
    SessionRepository,
    UserRepository,
    VacancyRepository,
)
from app.repositories.memory.stores import (
    MemoryAuthTokenRepository,
    MemoryCollectionRunRepository,
    MemoryFavoriteRepository,
    MemoryMatchRunRepository,
    MemoryMetricsRepository,
    MemoryModelRegistry,
    MemoryResumeRepository,
    MemorySessionRepository,
    MemoryUserRepository,
    MemoryVacancyRepository,
)


@dataclass(frozen=True, slots=True)
class Repositories:
    """Набор всех репозиториев."""

    models: ModelRegistry
    users: UserRepository
    sessions: SessionRepository
    tokens: AuthTokenRepository
    resumes: ResumeRepository
    vacancies: VacancyRepository
    favorites: FavoriteRepository
    match_runs: MatchRunRepository
    collection_runs: CollectionRunRepository
    metrics: MetricsRepository


def build_repositories(backend: str, database: Database | None = None, *, hnsw_ef_search: int = 300) -> Repositories:
    """Создаёт репозитории выбранного хранилища.

    Args:
        backend: значение ``STORAGE_BACKEND`` (``memory`` или ``postgres``).
        database: подключение к PostgreSQL; обязательно для ``postgres``.
        hnsw_ef_search: ``hnsw.ef_search`` при отборе кандидатов (только PostgreSQL).

    Raises:
        ValueError: хранилище не поддерживается или для ``postgres`` не передан ``database``.
    """
    if backend == "postgres":
        if database is None:
            raise ValueError("Для STORAGE_BACKEND=postgres нужен Database")
        return _build_postgres(database, hnsw_ef_search)
    if backend != "memory":
        raise ValueError(f"STORAGE_BACKEND={backend!r} не поддерживается: доступны 'memory' и 'postgres'")
    return Repositories(
        models=MemoryModelRegistry(),
        users=MemoryUserRepository(),
        sessions=MemorySessionRepository(),
        tokens=MemoryAuthTokenRepository(),
        resumes=MemoryResumeRepository(),
        vacancies=MemoryVacancyRepository(),
        favorites=MemoryFavoriteRepository(),
        match_runs=MemoryMatchRunRepository(),
        collection_runs=MemoryCollectionRunRepository(),
        metrics=MemoryMetricsRepository(),
    )


def _build_postgres(database: Database, hnsw_ef_search: int) -> Repositories:
    from app.repositories.postgres.collection import PgCollectionRunRepository
    from app.repositories.postgres.matching import PgFavoriteRepository, PgMatchRunRepository, PgMetricsRepository
    from app.repositories.postgres.registry import ActiveModels, PgModelRegistry
    from app.repositories.postgres.resumes import PgResumeRepository
    from app.repositories.postgres.users import PgAuthTokenRepository, PgSessionRepository, PgUserRepository
    from app.repositories.postgres.vacancies import PgVacancyRepository

    active = ActiveModels()
    return Repositories(
        models=PgModelRegistry(database, active),
        users=PgUserRepository(database),
        sessions=PgSessionRepository(database),
        tokens=PgAuthTokenRepository(database),
        resumes=PgResumeRepository(database, active),
        vacancies=PgVacancyRepository(database, active, hnsw_ef_search),
        favorites=PgFavoriteRepository(database),
        match_runs=PgMatchRunRepository(database, active),
        collection_runs=PgCollectionRunRepository(database),
        metrics=PgMetricsRepository(database),
    )
