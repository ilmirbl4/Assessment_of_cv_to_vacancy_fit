"""Сборка зависимостей приложения (один раз при создании приложения)."""

from __future__ import annotations

from dataclasses import dataclass

from app.collector.client import ApiClient
from app.collector.ingest import VacancyIngestor
from app.collector.service import ClientFactory, CollectionService
from app.config import Settings
from app.db.database import Database
from app.domain.clock import Clock, SystemClock
from app.ml.factory import MlComponents, build_ml
from app.repositories.factory import Repositories, build_repositories
from app.services.auth import AuthService
from app.services.email import ConsoleEmailSender, EmailSender, SmtpEmailSender
from app.services.matching import MatchingService
from app.services.rate_limit import MemoryRateLimiter, RateLimiter
from app.services.resume import ResumeService
from app.services.security import PasswordService
from app.services.tasks import TaskRegistry


@dataclass(slots=True)
class Container:
    """Все зависимости приложения."""

    settings: Settings
    clock: Clock
    database: Database | None
    repos: Repositories
    ml: MlComponents
    tasks: TaskRegistry
    passwords: PasswordService
    limiter: RateLimiter
    sender: EmailSender
    auth: AuthService
    resumes: ResumeService
    matching: MatchingService
    ingestor: VacancyIngestor
    collection: CollectionService


def _build_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "smtp":
        return SmtpEmailSender(
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_security,
            settings.smtp_user,
            settings.smtp_password,
            settings.smtp_from,
            settings.smtp_from_name,
            settings.smtp_timeout_s,
        )
    return ConsoleEmailSender()


def build_container(
    settings: Settings,
    *,
    clock: Clock | None = None,
    ml: MlComponents | None = None,
    sender: EmailSender | None = None,
    client_factory: ClientFactory | None = None,
) -> Container:
    """Создаёт контейнер; параметры позволяют тестам подменить внешние границы (часы, ML, почта, источник)."""
    # Сборщик и планировщик живут в этом процессе вместе с лимитером входа и блокировками подбора: воркер один.
    clock = clock or SystemClock()
    database: Database | None = None
    if settings.storage_backend == "postgres":
        if not settings.database_url:
            raise ValueError("STORAGE_BACKEND=postgres требует DATABASE_URL (без БД: STORAGE_BACKEND=memory)")
        database = Database(settings.database_url, settings.db_pool_min, settings.db_pool_max)
    repos = build_repositories(settings.storage_backend, database, hnsw_ef_search=settings.db_hnsw_ef_search)
    ml = ml or build_ml(settings)
    tasks = TaskRegistry()
    passwords = PasswordService(fast=settings.app_env == "test")
    limiter = MemoryRateLimiter(settings.login_max_failures)
    sender = sender or _build_sender(settings)
    ingestor = VacancyIngestor(repos.vacancies, ml, clock, settings.app_timezone)
    factory = client_factory or (lambda: ApiClient(settings.trudvsem_base_url))
    return Container(
        settings=settings,
        clock=clock,
        database=database,
        repos=repos,
        ml=ml,
        tasks=tasks,
        passwords=passwords,
        limiter=limiter,
        sender=sender,
        auth=AuthService(repos, passwords, limiter, sender, tasks, clock, settings),
        resumes=ResumeService(repos, ml, tasks, clock, settings),
        matching=MatchingService(repos, ml, clock, settings),
        ingestor=ingestor,
        collection=CollectionService(repos.collection_runs, repos.vacancies, ingestor, factory, clock, settings, tasks),
    )
