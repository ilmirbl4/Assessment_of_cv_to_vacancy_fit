import { useState } from 'react';
import { Star } from 'lucide-react';
import { errorMessage } from '../../api/client';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { LoadingRegion } from '../../components/ui/LoadingRegion';
import { PageTitle } from '../../components/ui/PageTitle';
import { Skeleton } from '../../components/ui/Skeleton';
import { useToast } from '../../components/ui/Toast';
import { QueryErrorView } from '../../components/layout/QueryErrorView';
import { FavoriteRow } from './FavoriteRow';
import { useFavorites, useRemoveFavorite } from './api';

export const EMPTY_FAVORITES_TEXT =
  'В избранном пока нет вакансий. Добавляйте их кнопкой «Добавить в избранное» на странице вакансии.';

/** Страница избранного (`/favorites`). */
export function FavoritesPage() {
  const query = useFavorites();
  const remove = useRemoveFavorite();
  const toast = useToast();
  const [removingId, setRemovingId] = useState<string | null>(null);

  function handleRemove(id: string) {
    setRemovingId(id);
    remove.mutate(id, {
      onSuccess: () => toast('Вакансия удалена из избранного'),
      onError: (e) => toast(errorMessage(e), 'danger'),
      onSettled: () => setRemovingId(null),
    });
  }

  return (
    <>
      <PageTitle title="Избранное" />
      <div className="mt-6 max-w-200">
        {query.isPending ? (
          <Card flush>
            <LoadingRegion>
              {Array.from({ length: 3 }, (_, i) => (
                <div key={i} className="space-y-2 border-b border-border px-6 py-4 last:border-b-0">
                  <Skeleton className="h-6 w-1/2" />
                  <Skeleton className="h-4 w-2/3" />
                </div>
              ))}
            </LoadingRegion>
          </Card>
        ) : query.isError ? (
          <QueryErrorView error={query.error} onRetry={() => void query.refetch()} />
        ) : query.data.length === 0 ? (
          <Card flush>
            <EmptyState icon={Star} title="Избранное пусто" description={EMPTY_FAVORITES_TEXT} />
          </Card>
        ) : (
          <Card flush>
            <ul>
              {query.data.map((item) => (
                <FavoriteRow
                  key={item.vacancy.id}
                  item={item}
                  removing={removingId === item.vacancy.id}
                  onRemove={() => handleRemove(item.vacancy.id)}
                />
              ))}
            </ul>
          </Card>
        )}
      </div>
    </>
  );
}
