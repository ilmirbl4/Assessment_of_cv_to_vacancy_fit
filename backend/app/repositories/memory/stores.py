"""Хранилища в памяти для тестов и локального запуска."""

from __future__ import annotations

import asyncio
from collections.abc import Collection, Sequence
from dataclasses import replace
from datetime import datetime

import numpy as np

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
    ResumeStatus,
    RunStatus,
    Session,
    TokenPurpose,
    UpsertResult,
    User,
    Vacancy,
    VacancyCandidate,
)
from app.repositories.errors import AlreadyExistsError


class MemoryModelRegistry:
    """Хранилище в памяти для тестов и локального запуска: запоминает активные спецификации по видам."""

    def __init__(self) -> None:
        """Создаёт пустой реестр."""
        self.active: dict[str, ModelSpec] = {}

    async def activate(self, specs: Sequence[ModelSpec]) -> None:
        """Делает переданные модели активными."""
        for spec in specs:
            self.active[spec.kind] = spec


class MemoryUserRepository:
    """Хранилище в памяти для тестов и локального запуска."""

    def __init__(self) -> None:
        """Создаёт пустое хранилище."""
        self._by_id: dict[str, User] = {}
        self._by_email: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get_by_id(self, user_id: str) -> User | None:
        """SELECT ... WHERE id = $1."""
        return self._by_id.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        """SELECT ... WHERE lower(email) = lower($1)."""
        user_id = self._by_email.get(email.lower())
        return self._by_id.get(user_id) if user_id else None

    async def create(self, user: User) -> None:
        """INSERT; уникальный индекс по lower(email)."""
        async with self._lock:
            key = user.email.lower()
            if key in self._by_email:
                raise AlreadyExistsError(key)
            self._by_id[user.id] = user
            self._by_email[key] = user.id

    async def update_password_hash(self, user_id: str, password_hash: str) -> None:
        """UPDATE users SET password_hash."""
        async with self._lock:
            user = self._by_id.get(user_id)
            if user:
                self._by_id[user_id] = replace(user, password_hash=password_hash)

    async def mark_email_confirmed(self, user_id: str, at: datetime) -> None:
        """UPDATE users SET email_confirmed_at."""
        async with self._lock:
            user = self._by_id.get(user_id)
            if user:
                self._by_id[user_id] = replace(user, email_confirmed_at=at)

    async def delete(self, user_id: str) -> None:
        """DELETE FROM users (ON DELETE CASCADE для зависимых таблиц)."""
        async with self._lock:
            user = self._by_id.pop(user_id, None)
            if user:
                self._by_email.pop(user.email.lower(), None)


class MemorySessionRepository:
    """Хранилище в памяти для тестов и локального запуска."""

    def __init__(self) -> None:
        """Создаёт пустое хранилище."""
        self._items: dict[str, Session] = {}

    async def create(self, session: Session) -> None:
        """INSERT INTO sessions."""
        self._items[session.token_hash] = session

    async def get(self, token_hash: str) -> Session | None:
        """SELECT по первичному ключу token_hash."""
        return self._items.get(token_hash)

    async def delete(self, token_hash: str) -> None:
        """DELETE по token_hash."""
        self._items.pop(token_hash, None)

    async def delete_all_for_user(self, user_id: str) -> None:
        """DELETE WHERE user_id."""
        for key in [k for k, v in self._items.items() if v.user_id == user_id]:
            del self._items[key]

    async def delete_expired(self, now: datetime) -> int:
        """DELETE WHERE expires_at <= now."""
        keys = [k for k, v in self._items.items() if v.expires_at <= now]
        for key in keys:
            del self._items[key]
        return len(keys)


class MemoryAuthTokenRepository:
    """Хранилище в памяти для тестов и локального запуска."""

    def __init__(self) -> None:
        """Создаёт пустое хранилище."""
        self._items: dict[str, AuthToken] = {}

    async def create(self, token: AuthToken) -> None:
        """INSERT INTO auth_tokens."""
        self._items[token.token_hash] = token

    async def get_valid(self, token_hash: str, purpose: TokenPurpose, now: datetime) -> AuthToken | None:
        """SELECT WHERE used_at IS NULL AND expires_at > now."""
        token = self._items.get(token_hash)
        if token and token.purpose == purpose and token.used_at is None and token.expires_at > now:
            return token
        return None

    async def mark_used(self, token_hash: str, at: datetime) -> None:
        """UPDATE SET used_at."""
        token = self._items.get(token_hash)
        if token:
            self._items[token_hash] = replace(token, used_at=at)

    async def invalidate_for_user(self, user_id: str, purpose: TokenPurpose) -> None:
        """DELETE WHERE user_id AND purpose."""
        for key in [k for k, v in self._items.items() if v.user_id == user_id and v.purpose == purpose]:
            del self._items[key]

    async def last_created_at(self, user_id: str, purpose: TokenPurpose) -> datetime | None:
        """SELECT max(created_at) WHERE user_id AND purpose."""
        moments = [v.created_at for v in self._items.values() if v.user_id == user_id and v.purpose == purpose]
        return max(moments) if moments else None

    async def delete_all_for_user(self, user_id: str) -> None:
        """DELETE WHERE user_id (ON DELETE CASCADE)."""
        for key in [k for k, v in self._items.items() if v.user_id == user_id]:
            del self._items[key]


class MemoryResumeRepository:
    """Хранилище в памяти для тестов и локального запуска."""

    def __init__(self) -> None:
        """Создаёт пустое хранилище."""
        self._items: dict[str, Resume] = {}
        self._lock = asyncio.Lock()

    async def get(self, user_id: str) -> Resume | None:
        """SELECT WHERE user_id (уникальный индекс по user_id)."""
        return self._items.get(user_id)

    async def replace(self, resume: Resume) -> None:
        """INSERT ... ON CONFLICT (user_id) DO UPDATE."""
        async with self._lock:
            self._items[resume.user_id] = resume

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
        """UPDATE ... WHERE user_id AND id = resume_id; число затронутых строк > 0."""
        async with self._lock:
            current = self._items.get(user_id)
            if current is None or current.id != resume_id:
                return False
            self._items[user_id] = replace(
                current,
                status=ResumeStatus(status),
                error_message=error_message,
                fragments=tuple(fragments),
                embedding=embedding,
                model_version=model_version,
                processed_at=processed_at,
            )
            return True

    async def delete(self, user_id: str) -> None:
        """DELETE WHERE user_id."""
        async with self._lock:
            self._items.pop(user_id, None)

    async def list_processing_started_before(self, moment: datetime) -> list[Resume]:
        """SELECT WHERE status = 'processing' AND uploaded_at < moment."""
        return [r for r in self._items.values() if r.status == ResumeStatus.PROCESSING and r.uploaded_at < moment]


class MemoryVacancyRepository:
    """Хранилище в памяти для тестов и локального запуска."""

    def __init__(self) -> None:
        """Создаёт пустое хранилище с индексами по кодам фильтров."""
        self._items: dict[str, Vacancy] = {}
        self._active: set[str] = set()
        self._index: dict[str, dict[str | None, set[str]]] = {
            "region": {},
            "employment": {},
            "schedule": {},
            "experience": {},
        }
        self._vectors: dict[str, np.ndarray] = {}
        self._lock = asyncio.Lock()

    def _index_add(self, vac: Vacancy) -> None:
        self._index["region"].setdefault(vac.region_code, set()).add(vac.id)
        self._index["employment"].setdefault(vac.employment_code, set()).add(vac.id)
        self._index["schedule"].setdefault(vac.schedule_code, set()).add(vac.id)
        self._index["experience"].setdefault(vac.experience_code, set()).add(vac.id)

    def _index_remove(self, vac: Vacancy) -> None:
        self._index["region"].get(vac.region_code, set()).discard(vac.id)
        self._index["employment"].get(vac.employment_code, set()).discard(vac.id)
        self._index["schedule"].get(vac.schedule_code, set()).discard(vac.id)
        self._index["experience"].get(vac.experience_code, set()).discard(vac.id)

    async def get(self, vacancy_id: str) -> Vacancy | None:
        """SELECT по первичному ключу."""
        return self._items.get(vacancy_id)

    async def get_many(self, ids: Collection[str]) -> dict[str, Vacancy]:
        """SELECT WHERE id = ANY($1)."""
        return {i: self._items[i] for i in ids if i in self._items}

    async def search_candidates(self, query: Embedding, filters: MatchFilters, limit: int) -> list[VacancyCandidate]:
        """Перебор скалярных произведений по активным вакансиям под фильтры."""
        selected: set[str] | None = None
        for key, value in (
            ("region", filters.region_code),
            ("employment", filters.employment_type),
            ("schedule", filters.schedule),
            ("experience", filters.experience),
        ):
            if value is not None:
                ids = self._index[key].get(value, set())
                selected = set(ids) if selected is None else selected & ids
        pool = self._active if selected is None else selected & self._active
        ids_in_pool: list[str] = []
        for vid in pool:
            if vid not in self._vectors:
                continue
            vac = self._items[vid]
            has_salary = vac.salary_from is not None or vac.salary_to is not None
            if filters.only_with_salary and not has_salary:
                continue
            if filters.min_salary is not None:
                top = vac.salary_to if vac.salary_to is not None else vac.salary_from
                if top is None or top < filters.min_salary:
                    continue
            ids_in_pool.append(vid)
        if not ids_in_pool or limit <= 0:
            return []
        matrix = np.stack([self._vectors[vid] for vid in ids_in_pool])
        scores = matrix @ np.frombuffer(query, dtype=np.float32)
        order = np.argsort(-scores)[:limit] if len(scores) > limit else range(len(scores))
        found = [
            VacancyCandidate(ids_in_pool[i], self._items[ids_in_pool[i]].published_at, float(scores[i])) for i in order
        ]
        found.sort(key=lambda c: (-c.score, -c.published_at.toordinal(), c.id))
        return found

    async def get_ingest_states(self, ids: Collection[str], model_version: str) -> dict[str, IngestState]:
        """Состояние вакансий; ``analysis_fresh`` — есть вектор и совпала ``model_version``."""
        states: dict[str, IngestState] = {}
        for vid in ids:
            old = self._items.get(vid)
            if old is not None:
                fresh = vid in self._vectors and old.model_version == model_version
                states[vid] = IngestState(old.date_modify, old.content_hash, old.is_active, fresh)
        return states

    async def upsert_batch(
        self,
        vacancies: Sequence[Vacancy],
        *,
        keep_analysis: Collection[str] = (),
        ingestion_run_id: str | None = None,
    ) -> UpsertResult:
        """Вставка, обновление или пропуск по правилам раздела 6.2 инструкции."""
        new = updated = unchanged = 0
        keep = keep_analysis if isinstance(keep_analysis, set) else set(keep_analysis)
        async with self._lock:
            for vac in vacancies:
                old = self._items.get(vac.id)
                if old is None:
                    new += 1
                    stored = vac
                elif (
                    old.date_modify != vac.date_modify
                    or old.content_hash != vac.content_hash
                    or old.model_version != vac.model_version
                    or not old.is_active
                ):
                    updated += 1
                    stored = replace(vac, first_seen_at=old.first_seen_at)
                    if vac.is_active:
                        stored = replace(stored, deactivated_at=None)
                    self._index_remove(old)
                else:
                    unchanged += 1
                    continue
                if old is not None and vac.id in keep:
                    stored = replace(
                        stored, requirements=old.requirements, embedding=old.embedding, model_version=old.model_version
                    )
                if not stored.is_active:
                    stored = replace(stored, embedding=None, deactivated_at=stored.deactivated_at or stored.updated_at)
                self._items[vac.id] = stored
                self._index_add(stored)
                if stored.is_active:
                    self._active.add(stored.id)
                else:
                    self._active.discard(stored.id)
                if stored.embedding is not None:
                    self._vectors[stored.id] = np.frombuffer(stored.embedding, dtype=np.float32).copy()
                else:
                    self._vectors.pop(stored.id, None)
        return UpsertResult(new, updated, unchanged)

    def _close(self, vid: str, at: datetime) -> None:
        self._items[vid] = replace(self._items[vid], is_active=False, deactivated_at=at, updated_at=at, embedding=None)
        self._active.discard(vid)
        self._vectors.pop(vid, None)

    async def deactivate_missing(self, seen_ids: Collection[str], at: datetime) -> int:
        """Деактивирует активные вакансии вне ``seen_ids``, удаляя их векторы."""
        seen = seen_ids if isinstance(seen_ids, set) else set(seen_ids)
        async with self._lock:
            gone = self._active - seen
            for vid in gone:
                self._close(vid, at)
            return len(gone)

    async def deactivate_ids(self, ids: Collection[str], at: datetime) -> int:
        """Деактивирует перечисленные активные вакансии, удаляя их векторы."""
        async with self._lock:
            gone = {i for i in ids if i in self._active}
            for vid in gone:
                self._close(vid, at)
            return len(gone)

    async def count_active(self) -> int:
        """SELECT count(*) WHERE is_active."""
        return len(self._active)


class MemoryFavoriteRepository:
    """Хранилище в памяти для тестов и локального запуска."""

    def __init__(self) -> None:
        """Создаёт пустое хранилище."""
        self._items: dict[tuple[str, str], Favorite] = {}
        self._lock = asyncio.Lock()

    async def list_for_user(self, user_id: str) -> list[Favorite]:
        """SELECT WHERE user_id ORDER BY added_at DESC."""
        items = [f for (uid, _), f in self._items.items() if uid == user_id]
        return sorted(items, key=lambda f: f.added_at, reverse=True)

    async def add(self, favorite: Favorite) -> None:
        """INSERT; первичный ключ (user_id, vacancy_id)."""
        async with self._lock:
            key = (favorite.user_id, favorite.vacancy_id)
            if key in self._items:
                raise AlreadyExistsError(str(key))
            self._items[key] = favorite

    async def remove(self, user_id: str, vacancy_id: str) -> bool:
        """DELETE WHERE user_id AND vacancy_id."""
        async with self._lock:
            return self._items.pop((user_id, vacancy_id), None) is not None

    async def exists(self, user_id: str, vacancy_id: str) -> bool:
        """SELECT EXISTS по первичному ключу."""
        return (user_id, vacancy_id) in self._items

    async def delete_all_for_user(self, user_id: str) -> None:
        """DELETE WHERE user_id (ON DELETE CASCADE)."""
        async with self._lock:
            for key in [k for k in self._items if k[0] == user_id]:
                del self._items[key]


class MemoryMatchRunRepository:
    """Хранилище в памяти для тестов и локального запуска."""

    def __init__(self) -> None:
        """Создаёт пустое хранилище."""
        self._items: dict[str, MatchRun] = {}

    async def get_current(self, user_id: str) -> MatchRun | None:
        """SELECT WHERE user_id (один подбор на пользователя)."""
        return self._items.get(user_id)

    async def save_current(self, run: MatchRun) -> None:
        """INSERT ... ON CONFLICT (user_id) DO UPDATE."""
        self._items[run.user_id] = run

    async def delete_for_user(self, user_id: str) -> None:
        """DELETE WHERE user_id (ON DELETE CASCADE)."""
        self._items.pop(user_id, None)


class MemoryCollectionRunRepository:
    """Хранилище в памяти для тестов и локального запуска."""

    def __init__(self) -> None:
        """Создаёт пустое хранилище."""
        self._items: dict[str, CollectionRun] = {}

    async def create(self, run: CollectionRun) -> None:
        """INSERT INTO collection_runs."""
        self._items[run.id] = run

    async def update(self, run: CollectionRun) -> None:
        """UPDATE collection_runs."""
        self._items[run.id] = run

    async def get_running(self) -> CollectionRun | None:
        """SELECT WHERE status = 'running'."""
        return next((r for r in self._items.values() if r.status == RunStatus.RUNNING), None)

    async def get_last_complete(self) -> CollectionRun | None:
        """SELECT WHERE complete ORDER BY snapshot_at DESC LIMIT 1."""
        done = [r for r in self._items.values() if r.complete]
        return max(done, key=lambda r: r.snapshot_at) if done else None

    async def list_started_since(self, moment: datetime) -> list[CollectionRun]:
        """SELECT WHERE started_at >= moment ORDER BY started_at DESC."""
        items = [r for r in self._items.values() if r.started_at >= moment]
        return sorted(items, key=lambda r: r.started_at, reverse=True)

    async def fail_running(self, at: datetime, message: str) -> int:
        """UPDATE SET status = 'failed' WHERE status = 'running'."""
        count = 0
        for key, run in list(self._items.items()):
            if run.status == RunStatus.RUNNING:
                self._items[key] = replace(run, status=RunStatus.FAILED, finished_at=at, error_message=message)
                count += 1
        return count


class MemoryMetricsRepository:
    """Хранилище в памяти для тестов и локального запуска."""

    def __init__(self) -> None:
        """Создаёт пустое хранилище."""
        self.matching: list[MatchingEvent] = []
        self.favorites_from_run: dict[str, FavoriteFromRunEvent] = {}

    async def record_matching(self, event: MatchingEvent) -> None:
        """INSERT INTO matching_events."""
        self.matching.append(event)

    async def record_favorite_from_run(self, event: FavoriteFromRunEvent) -> None:
        """INSERT ... ON CONFLICT (run_id) DO NOTHING."""
        self.favorites_from_run.setdefault(event.run_id, event)

    async def count_favorites_from_run(self) -> int:
        """Число подборов, из которых что-то добавлено в избранное."""
        return len(self.favorites_from_run)
