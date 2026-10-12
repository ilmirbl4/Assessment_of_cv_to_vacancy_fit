import type { ApiErrorBody } from './types';

/** Базовый путь REST API. */
export const API_BASE = '/api/v1';

export const MSG_SERVER = 'Произошла ошибка на сервере. Повторите попытку позже.';
export const MSG_NETWORK = 'Не удалось связаться с сервером. Проверьте подключение и повторите попытку.';

/** Ошибка, пришедшая от сервера (статус 4xx/5xx). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, string>;

  /**
   * @param status HTTP-статус
   * @param code машинный код ошибки
   * @param message сообщение на русском
   * @param fields ошибки по полям формы
   */
  constructor(status: number, code: string, message: string, fields: Record<string, string> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

/** Сетевая ошибка: сервер недоступен. */
export class NetworkError extends Error {
  constructor() {
    super(MSG_NETWORK);
    this.name = 'NetworkError';
  }
}

/**
 * Возвращает текст ошибки для показа пользователю.
 * @param error произвольная ошибка
 */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.status >= 500 ? MSG_SERVER : error.message;
  if (error instanceof NetworkError) return MSG_NETWORK;
  return MSG_SERVER;
}

type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

/**
 * Регистрирует обработчик ответа 401 (очистка кэша и переход на вход).
 * @param handler функция-обработчик или null
 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

/** Пути, для которых ответ 401 не вызывает общий переход на вход. */
const NO_REDIRECT_ON_401 = new Set(['GET /auth/me', 'POST /auth/login']);

export interface RequestOptions {
  body?: unknown;
  form?: FormData;
  query?: Record<string, string | number | undefined>;
}

/**
 * Выполняет запрос к API с cookie-аутентификацией и единым разбором ошибок.
 * @param method HTTP-метод
 * @param path путь относительно /api/v1
 * @param options тело (JSON или форма) и параметры запроса
 * @returns разобранный JSON или undefined для пустых ответов
 */
export async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, globalThis.location.origin);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }

  const init: RequestInit = { method, credentials: 'include', headers: { Accept: 'application/json' } };
  if (options.form) {
    init.body = options.form;
  } else if (options.body !== undefined) {
    init.body = JSON.stringify(options.body);
    init.headers = { ...init.headers, 'Content-Type': 'application/json' };
  }

  let response: Response;
  try {
    response = await fetch(url.toString(), init);
  } catch {
    throw new NetworkError();
  }

  if (response.ok) {
    if (response.status === 204) return undefined as T;
    const text = await response.text();
    return (text ? JSON.parse(text) : undefined) as T;
  }

  let body: Partial<ApiErrorBody> = {};
  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    body = {};
  }
  const error = new ApiError(
    response.status,
    body.error?.code ?? 'UNKNOWN',
    body.error?.message ?? MSG_SERVER,
    body.error?.fields,
  );
  if (response.status === 401 && !NO_REDIRECT_ON_401.has(`${method} ${path}`)) {
    unauthorizedHandler?.();
  }
  throw error;
}
