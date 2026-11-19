"""Сборка зависимостей приложения (один раз при создании приложения)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.collector.client import ApiClient
from app.collector.ingest import VacancyIngestor
from app.collector.service import ClientFactory, CollectionService
from app.config import Settings
from app.db.database import Database
from app.domain.clock import Clock, SystemClock
from app.ml.factory import MlComponents, build_ml
from app.repositories.factory import Repositories, build_repositories
from app.services.auth import AuthService
from app.services.email import EmailSender, SmtpEmailSender
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
    database: Database
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
    monitoring: Any = None
    controller: Any = None
    pipeline_id: str = ""


def _build_sender(settings: Settings) -> EmailSender:
    if not all((settings.smtp_host, settings.smtp_from, settings.smtp_user, settings.smtp_password)):
        raise ValueError("Заполните SMTP_HOST, SMTP_FROM, SMTP_USER и SMTP_PASSWORD в backend/.env")
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


def build_container(
    settings: Settings,
    database: Database,
    *,
    clock: Clock | None = None,
    ml: MlComponents | None = None,
    sender: EmailSender | None = None,
    client_factory: ClientFactory | None = None,
) -> Container:
    """Создаёт контейнер; параметры позволяют тестам подменить внешние границы (часы, ML, почта, источник)."""
    # Сборщик и планировщик живут в этом процессе вместе с лимитером входа и блокировками подбора: воркер один.
    clock = clock or SystemClock()

    repos = build_repositories(database, hnsw_ef_search=settings.db_hnsw_ef_search)

    # создание объекта класса MlComponents, который содержит все ML-компоненты:
    # NER = RequirementExtractor
    # нарезка резюме на чанки = ResumeSegmenter
    # би-энкодер = BiEncoder
    # кросс-энкодер = PairScorer
    ml = ml or build_ml(settings)

    tasks = TaskRegistry()  # пустой регистр фоновых задач

    # быстрое хеширование паролей для тестов, медленное для продакшена
    passwords = PasswordService(fast=settings.app_env == "test")

    # ограничитель неудачных попыток входа
    limiter = MemoryRateLimiter(settings.login_max_failures)

    # создание отправителя почты SMTP
    sender = sender or _build_sender(settings)

    # создание сборщика вакансий, внутри него
    # создание клиента API для доступа к внешнему источнику вакансий (Trudvsem)
    # создание пайплайна обработки вакансий (API, предобработка, NER, би-энкодер)
    ingestor = VacancyIngestor(repos.vacancies, ml, clock, settings.app_timezone)
    factory = client_factory or (
        lambda: ApiClient(settings.trudvsem_base_url, max_attempts=settings.collector_max_attempts)
    )

    container = Container(
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

    from app.collector.controller import Controller
    from app.ml.factory import pipeline_id
    from app.monitoring.service import Monitoring

    container.pipeline_id = pipeline_id(ml, settings)
    container.monitoring = Monitoring(container)
    container.controller = Controller(container)
    repos.vacancies.monitoring = container.monitoring
    return container
