import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/endpoints';
import { ApiError } from '../../api/client';
import type { User } from '../../api/types';

export const ME_KEY = ['me'] as const;

/**
 * Текущий пользователь из `GET /auth/me` (кэш ['me']). Ответ 401 означает гостя и даёт null.
 */
export function useMe() {
  return useQuery<User | null>({
    queryKey: ME_KEY,
    queryFn: async () => {
      try {
        return await api.me();
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: Infinity,
  });
}

/** Мутация входа: после успеха записывает пользователя в кэш ['me']. */
export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.login,
    onSuccess: (user) => client.setQueryData(ME_KEY, user),
  });
}

let intentionalExit = false;

/** Признак того, что пользователь сам завершил сессию (тогда вход открывается без `next`). */
export function isIntentionalExit(): boolean {
  return intentionalExit;
}

/** Сбрасывает признак добровольного выхода (при открытии страницы входа). */
export function resetIntentionalExit(): void {
  intentionalExit = false;
}

/**
 * Возвращает функцию завершения сессии на клиенте: отменяет запросы, удаляет весь кэш
 * (эквивалент `queryClient.clear()`) и записывает в ['me'] значение «гость».
 * Так открытые страницы уходят на вход до того, как начнут перезапрашивать данные.
 */
export function useEndSession() {
  const client = useQueryClient();
  return () => {
    intentionalExit = true;
    void client.cancelQueries();
    client.removeQueries({ predicate: (q) => q.queryKey[0] !== ME_KEY[0] });
    client.setQueryData(ME_KEY, null);
  };
}

/** Мутация выхода: после ответа сервера очищает кэш React Query. */
export function useLogout() {
  const endSession = useEndSession();
  return useMutation({ mutationFn: api.logout, onSuccess: endSession });
}

/** Домашний маршрут роли. */
export function homePath(role: User['role']): string {
  return role === 'admin' ? '/admin/collection' : '/';
}
