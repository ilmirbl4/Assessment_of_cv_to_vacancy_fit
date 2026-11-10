"""Наполнение заглушек хранилища (раздел 9 инструкции)."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from array import array
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from app.collector.ingest import analyse_vacancies
from app.collector.normalizer import normalize
from app.container import Container
from app.domain.models import Favorite, Resume, ResumeStatus, Role, User, Vacancy
from app.reference import regions
from app.repositories.errors import AlreadyExistsError
from app.repositories.interfaces import VacancyRepository

log = logging.getLogger("app.seed")


class _Lcg:
    """Простой детерминированный генератор псевдослучайных чисел (синтетика не требует криптостойкости)."""

    def __init__(self, seed: int) -> None:
        self._state = seed

    def below(self, bound: int) -> int:
        """Следующее число в диапазоне ``0 <= x < bound``."""
        self._state = (self._state * 6364136223846793005 + 1442695040888963407) % (1 << 64)
        return (self._state >> 33) % bound


FIXTURES = Path(__file__).parent / "fixtures"
ARCHIVED_ID = "00000000-0000-4000-8000-000000000040"
BATCH = 500


def load_fixture_vacancies() -> list[dict[str, Any]]:
    """Сырые вакансии демо-набора (формат trudvsem)."""
    data: list[dict[str, Any]] = json.loads((FIXTURES / "vacancies_raw.json").read_text(encoding="utf-8"))
    return data


async def seed_demo(container: Container) -> None:
    """Создаёт демо-пользователей, вакансии, резюме и избранное."""
    repos, now = container.repos, container.clock.now()

    async def add_user(email: str, password: str, role: Role, confirmed: bool) -> User:
        existing = await repos.users.get_by_email(email)
        if existing is not None:
            return existing
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=container.passwords.hash(password),
            role=role,
            email_confirmed_at=now if confirmed else None,
            consent_version="1.0" if role == Role.SEEKER else None,
            consent_accepted_at=now if role == Role.SEEKER else None,
            created_at=now,
        )
        await repos.users.create(user)
        return user

    seeker = await add_user("seeker@example.com", "Password1", Role.SEEKER, True)
    await add_user("noresume@example.com", "Password1", Role.SEEKER, True)
    await add_user("unconfirmed@example.com", "Password1", Role.SEEKER, False)
    await add_user("admin@example.com", "Admin1234", Role.ADMIN, True)

    result = await container.ingestor.ingest(load_fixture_vacancies())
    await repos.vacancies.deactivate_ids({ARCHIVED_ID}, now)

    await _give_resume(container, seeker)
    for n in range(container.settings.seed_perf_users):
        await _give_resume(container, await add_user(f"perf{n}@example.com", "Password1", Role.SEEKER, True))

    ids = sorted(result.seen_ids)
    for offset, vacancy_id in enumerate((ids[0], ids[1], ARCHIVED_ID)):
        try:
            await repos.favorites.add(Favorite(seeker.id, vacancy_id, now - timedelta(hours=offset + 1)))
        except AlreadyExistsError:
            continue
    log.info("Демо-данные загружены: %d вакансий", len(ids))


async def _give_resume(container: Container, user: User) -> None:
    if await container.repos.resumes.get(user.id) is not None:
        return
    text = (FIXTURES / "resume_seeker.txt").read_text(encoding="utf-8")
    resume = Resume(
        id=str(uuid.uuid4()),
        user_id=user.id,
        file_name="Иванов_Пётр_резюме.docx",
        file_type="docx",
        uploaded_at=container.clock.now(),
        status=ResumeStatus.PROCESSING,
        error_message=None,
        text=text,
    )
    await container.repos.resumes.replace(resume)
    await container.resumes.process(resume)


async def seed_dataset(container: Container, directory: str, limit: int) -> int:
    """Загружает реальные вакансии из каталога ``*.json`` (ключ ``vacancies``) через общий конвейер."""
    loaded = 0
    batch: list[dict[str, Any]] = []
    for path in sorted(Path(directory).glob("*.json")):
        for raw in json.loads(path.read_text(encoding="utf-8")).get("vacancies", []):
            batch.append(raw)
            loaded += 1
            if len(batch) >= BATCH:
                await container.ingestor.ingest(batch)
                batch = []
            if loaded >= limit:
                break
        if loaded >= limit:
            break
    if batch:
        await container.ingestor.ingest(batch)
    log.info("Загружено вакансий из датасета: %d", loaded)
    return loaded


async def seed_synthetic(container: Container, count: int) -> None:
    """Генерирует ``count`` детерминированных вакансий напрямую в доменном виде (для нагрузочных замеров)."""
    now = container.clock.now()
    norms = [normalize(raw) for raw in load_fixture_vacancies()]
    templates = await asyncio.to_thread(analyse_vacancies, norms, container.ml, now)
    rng = _Lcg(20261025)
    codes = [o.code for o in regions()]
    names = {o.code: o.name for o in regions()}
    base = date(2026, 10, 25)
    batch: list[Vacancy] = []
    repo: VacancyRepository = container.repos.vacancies
    for i in range(count):
        tpl = templates[i % len(templates)]
        if tpl.embedding is None:
            raise ValueError("analyse_vacancies не вернула вектор шаблона")
        template = np.frombuffer(tpl.embedding, dtype=np.float32)
        noise = np.random.default_rng(i).standard_normal(template.shape[0])
        noise /= np.linalg.norm(noise)
        shifted = template + 0.3 * noise
        vector = array("f", (shifted / np.linalg.norm(shifted)).astype(np.float32).tolist())
        code = codes[rng.below(len(codes))]
        salary = [None, 40000, 90000, 150000, 250000][rng.below(5)]
        batch.append(
            replace(
                tpl,
                id=f"synthetic-{i:07d}",
                published_at=base - timedelta(days=rng.below(60)),
                region_code=code,
                region_name=names[code],
                salary_from=salary,
                salary_to=None if salary is None else salary + 50000,
                is_active=True,
                embedding=vector,
            )
        )
        if len(batch) >= 5000:
            await repo.upsert_batch(batch)
            batch = []
    if batch:
        await repo.upsert_batch(batch)
    log.info("Синтетических вакансий: %d", count)
