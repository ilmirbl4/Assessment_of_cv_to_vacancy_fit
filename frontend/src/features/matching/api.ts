import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../../api/client';
import { api } from '../../api/endpoints';
import type { MatchFilters, MatchPage } from '../../api/types';

export const matchKey = (page: number) => ['match', 'current', page] as const;

/** Справочники для фильтров (`GET /dictionaries`). */
export function useDictionaries() {
  return useQuery({ queryKey: ['dictionaries'], queryFn: api.dictionaries, staleTime: Infinity });
}

/**
 * Страница результатов последнего подбора; 404 NO_MATCH_RUN даёт null.
 * @param page номер страницы с 1
 */
export function useCurrentMatch(page: number) {
  return useQuery<MatchPage | null>({
    queryKey: matchKey(page),
    queryFn: async () => {
      try {
        return await api.currentMatching(page);
      } catch (e) {
        if (e instanceof ApiError && e.code === 'NO_MATCH_RUN') return null;
        throw e;
      }
    },
  });
}

/** Запуск подбора: новый результат заменяет старый и становится страницей 1 в кэше. */
export function useStartMatching() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (filters: MatchFilters) => api.startMatching(filters),
    onSuccess: (result) => {
      client.removeQueries({ queryKey: ['match'] });
      client.setQueryData(matchKey(1), result);
    },
  });
}
