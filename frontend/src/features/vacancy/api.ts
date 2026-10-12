import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../../api/client';
import { api } from '../../api/endpoints';
import type { VacancyDetail } from '../../api/types';

export const vacancyKey = (id: string) => ['vacancy', id] as const;

/**
 * Полные данные вакансии (`GET /vacancies/{id}`).
 * @param id идентификатор вакансии
 */
export function useVacancy(id: string) {
  return useQuery({ queryKey: vacancyKey(id), queryFn: () => api.vacancy(id) });
}

/** Добавление вакансии в избранное; страница обновляется без перезагрузки. */
export function useAddFavorite(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      try {
        await api.addFavorite(id);
      } catch (e) {
        if (!(e instanceof ApiError && e.code === 'ALREADY_IN_FAVORITES')) throw e;
      }
    },
    onSuccess: () => {
      client.setQueryData<VacancyDetail>(vacancyKey(id), (old) => (old ? { ...old, is_favorite: true } : old));
      void client.invalidateQueries({ queryKey: ['favorites'] });
    },
  });
}
