import { HttpResponse, delay, http } from 'msw';
import type { ApiErrorBody, Role } from '../../api/types';
import { type DbState, type DbUser, extraDelay, failList, getSessionEmail, loadDb } from '../db';

export const API = '/api/v1';

/**
 * Формирует ответ с ошибкой в формате контракта.
 * @param status HTTP-статус
 * @param code машинный код
 * @param message сообщение на русском
 * @param fields ошибки по полям
 */
export function err(status: number, code: string, message: string, fields?: Record<string, string>) {
  const body: ApiErrorBody = { error: { code, message, fields } };
  return HttpResponse.json(body, { status });
}

/** Ответ 204 без тела. */
export function noContent() {
  return new HttpResponse(null, { status: 204 });
}

type Method = 'get' | 'post' | 'put' | 'delete';
type Info = Parameters<Parameters<typeof http.get>[1]>[0];

/**
 * Регистрирует обработчик: задержка, принудительная ошибка `mock:fail`, вызов resolver.
 * @param method HTTP-метод
 * @param path путь относительно /api/v1
 * @param resolver функция-обработчик
 */
export function route(method: Method, path: string, resolver: (info: Info) => Response | Promise<Response>) {
  return http[method](`${API}${path}`, async (info) => {
    await delay();
    if (extraDelay() > 0) await delay(extraDelay());
    const key = `${method.toUpperCase()} ${new URL(info.request.url).pathname}`;
    if (failList().includes(key)) {
      return err(500, 'SERVER_ERROR', 'Произошла ошибка на сервере. Повторите попытку позже.');
    }
    return resolver(info);
  });
}

export type Auth = { db: DbState; user: DbUser } | { response: Response };

/**
 * Проверяет сессию и роль.
 * @param role требуемая роль или undefined (любая)
 * @returns пользователь и состояние либо готовый ответ 401/403
 */
export function authorize(role?: Role): Auth {
  const db = loadDb();
  const email = getSessionEmail();
  const user = email ? db.users.find((u) => u.email === email) : undefined;
  if (!user) return { response: err(401, 'UNAUTHORIZED', 'Требуется вход в систему') };
  if (role && user.role !== role) return { response: err(403, 'FORBIDDEN', 'Недостаточно прав') };
  return { db, user };
}
