"""Выбор реализации хранилища по настройке ``STORAGE_BACKEND``."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.database import Database
from app.repositories.interfaces import (
    AuthTokenRepository,
    CollectionRunRepository,
    FavoriteRepository,
    MetricsRepository,
    SessionRepository,
    UserRepository,
)
from app.repositories.postgres.matching import PgMatchRunRepository
from app.repositories.postgres.registry import PgModelRegistry
from app.repositories.postgres.resumes import PgResumeRepository
from app.repositories.postgres.vacancies import PgVacancyRepository


@dataclass(frozen=True, slots=True)
class Repositories:
    """Набор всех репозиториев."""

    models: PgModelRegistry
    users: UserRepository
    sessions: SessionRepository
    tokens: AuthTokenRepository
    resumes: PgResumeRepository
    vacancies: PgVacancyRepository
    favorites: FavoriteRepository
    match_runs: PgMatchRunRepository
    collection_runs: CollectionRunRepository
    metrics: MetricsRepository


def build_repositories(database: Database, *, hnsw_ef_search: int = 300) -> Repositories:
    """Создаёт репозитории PostgreSQL, использующие общий пул."""
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
