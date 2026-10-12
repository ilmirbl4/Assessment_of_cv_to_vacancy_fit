import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/endpoints';
import type { FavoriteItem } from '../../api/types';

export const FAVORITES_KEY = ['favorites'] as const;

/** Список избранного (`GET /favorites`). */
export function useFavorites() {
  return useQuery({ queryKey: FAVORITES_KEY, queryFn: api.favorites });
}

/** Удаление вакансии из избранного: карточка исчезает из кэша, кэш страницы вакансии сбрасывается. */
export function useRemoveFavorite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.removeFavorite(id),
    onSuccess: (_, id) => {
      client.setQueryData<FavoriteItem[]>(FAVORITES_KEY, (old) => old?.filter((f) => f.vacancy.id !== id));
      client.removeQueries({ queryKey: ['vacancy', id] });
    },
  });
}
