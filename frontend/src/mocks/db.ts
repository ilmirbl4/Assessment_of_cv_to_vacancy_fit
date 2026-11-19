import type { CollectionRun, MatchFilters, Role } from '../api/types';
import { SEEKER_FAVORITES, SEEKER_SKILLS, SEED_USERS } from './seed';

/** Состояние моков в localStorage (`mock:db`), сессия — `mock:session` (раздел 5). */

export const DB_KEY = 'mock:db';
export const SESSION_KEY = 'mock:session';
export const FAIL_KEY = 'mock:fail';

/** Настраиваемые задержки фоновых процессов (мс); в тестах можно обнулить. */
export const mockConfig = { resumeProcessingMs: 3000, collectionMs: 5000 };

export interface DbUser {
  id: string;
  email: string;
  password: string;
  role: Role;
  confirmed: boolean;
  via_ui?: boolean;
}

export interface DbResume {
  file_name: string;
  uploaded_at: string;
  ready_at: number;
  outcome: 'ready' | 'failed';
  /** Содержимое резюме для имитации кросс-энкодера; клиенту не отдаётся. */
  skills: string[];
}

export interface StoredRun {
  run_id: string;
  created_at: string;
  filters: MatchFilters;
  ids: string[];
}

export interface DbState {
  users: DbUser[];
  resumes: Record<string, DbResume>;
  favorites: Record<string, { vacancy_id: string; added_at: string }[]>;
  runs: Record<string, StoredRun>;
  collection_added: CollectionRun[];
  collection_running_until: number | null;
  collection_running_id: string | null;
  counter: number;
  reset_email: string | null;
}

/** Создаёт начальное состояние из фикстур. */
export function createSeedState(): DbState {
  return {
    users: SEED_USERS.map((u) => ({ ...u })),
    resumes: {
      u1: {
        file_name: 'ivanov_cv.pdf',
        uploaded_at: '2026-10-12T14:05:00+03:00',
        ready_at: 0,
        outcome: 'ready',
        skills: [...SEEKER_SKILLS],
      },
    },
    favorites: { u1: SEEKER_FAVORITES.map((f) => ({ ...f })) },
    runs: {},
    collection_added: [],
    collection_running_until: null,
    collection_running_id: null,
    counter: 1,
    reset_email: null,
  };
}

/** Читает состояние из localStorage или создаёт из фикстур. */
export function loadDb(): DbState {
  const raw = localStorage.getItem(DB_KEY);
  if (raw) {
    try {
      return JSON.parse(raw) as DbState;
    } catch {
      /* повреждённое состояние пересоздаётся */
    }
  }
  const fresh = createSeedState();
  saveDb(fresh);
  return fresh;
}

/** Сохраняет состояние в localStorage. */
export function saveDb(db: DbState): void {
  localStorage.setItem(DB_KEY, JSON.stringify(db));
}

/** Сбрасывает состояние моков к фикстурам (для тестов). */
export function resetDb(): void {
  localStorage.removeItem(DB_KEY);
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(FAIL_KEY);
}

/** Возвращает email текущей сессии или null. */
export function getSessionEmail(): string | null {
  return localStorage.getItem(SESSION_KEY);
}

/** Устанавливает или сбрасывает сессию. */
export function setSessionEmail(email: string | null): void {
  if (email) localStorage.setItem(SESSION_KEY, email);
  else localStorage.removeItem(SESSION_KEY);
}

/** Дополнительная задержка ответов (мс) из `mock:delay` — нужна, чтобы снять скриншоты состояния «загрузка». */
export function extraDelay(): number {
  const value = Number(localStorage.getItem('mock:delay') ?? 0);
  return Number.isFinite(value) && value > 0 ? value : 0;
}

/** Список запросов, на которые мок обязан ответить 500 (`mock:fail`). */
export function failList(): string[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(FAIL_KEY) ?? '[]');
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === 'string') : [];
  } catch {
    return [];
  }
}
