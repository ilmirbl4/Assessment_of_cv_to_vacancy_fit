import { useQuery } from '@tanstack/react-query';
import { api } from '../api/endpoints';
import { QueryErrorView } from '../components/layout/QueryErrorView';
import { Card } from '../components/ui/Card';
import { PageTitle } from '../components/ui/PageTitle';
import { Skeleton } from '../components/ui/Skeleton';
import { LoadingRegion } from '../components/ui/LoadingRegion';
import { formatDate } from '../lib/format';

/** Текст согласия на обработку персональных данных (`GET /consent/current`). */
export function ConsentPage() {
  const query = useQuery({ queryKey: ['consent'], queryFn: api.consent });
  return (
    <div className="max-w-200">
      <PageTitle title="Согласие на обработку персональных данных" documentTitle="Согласие" />
      <div className="mt-6">
        {query.isPending ? (
          <LoadingRegion>
            <Skeleton className="h-48 w-full" />
          </LoadingRegion>
        ) : query.isError ? (
          <QueryErrorView error={query.error} onRetry={() => void query.refetch()} />
        ) : (
          <Card>
            <p className="whitespace-pre-line">{query.data.text}</p>
            <p className="mt-4 text-sm text-text-muted">
              Версия {query.data.version} от {formatDate(query.data.published_at)}
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
