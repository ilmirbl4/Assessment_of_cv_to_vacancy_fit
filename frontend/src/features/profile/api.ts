import type { RefObject } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../../api/client';
import { api } from '../../api/endpoints';
import type { Resume } from '../../api/types';
import { useEndSession } from '../auth/api';

export const RESUME_KEY = ['resume'] as const;
export const POLL_MS = 2000;
export const SLOW_AFTER_MS = 30_000;
export const GIVE_UP_AFTER_MS = 120_000;

/**
 * Текущее резюме (`GET /resume`); 404 даёт null. Пока статус `processing`, опрашивает сервер каждые 2 с.
 * @param stopRef ссылка-флаг: когда `current === true`, опрос прекращается (после 120 с ожидания)
 */
export function useResume(stopRef?: RefObject<boolean>) {
  return useQuery<Resume | null>({
    queryKey: RESUME_KEY,
    queryFn: async () => {
      try {
        return await api.resume();
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    refetchInterval: (query) =>
      !stopRef?.current && query.state.data?.status === 'processing' ? POLL_MS : false,
  });
}

/** Загрузка (замена) резюме: после успеха кладёт ответ в кэш и сбрасывает результаты подбора. */
export function useUploadResume() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.uploadResume,
    onSuccess: (resume) => {
      client.setQueryData(RESUME_KEY, resume);
      client.removeQueries({ queryKey: ['match'] });
    },
  });
}

/** Удаление резюме. */
export function useDeleteResume() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.deleteResume,
    onSuccess: () => {
      client.setQueryData(RESUME_KEY, null);
      client.removeQueries({ queryKey: ['match'] });
    },
  });
}

/** Удаление учётной записи: после ответа сервера очищает кэш и завершает сессию. */
export function useDeleteAccount() {
  const endSession = useEndSession();
  return useMutation({ mutationFn: api.deleteAccount, onSuccess: endSession });
}
