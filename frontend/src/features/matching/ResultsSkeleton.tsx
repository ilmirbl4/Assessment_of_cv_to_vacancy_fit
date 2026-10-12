import { Card } from '../../components/ui/Card';
import { LoadingRegion } from '../../components/ui/LoadingRegion';
import { Skeleton } from '../../components/ui/Skeleton';

/** Скелетон списка результатов: 10 строк, повторяющих форму карточки. */
export function ResultsSkeleton() {
  return (
    <Card flush>
      <LoadingRegion>
        <div className="border-b border-border px-6 py-4">
          <Skeleton className="h-6 w-48" />
        </div>
        {Array.from({ length: 10 }, (_, i) => (
          <div key={i} className="flex items-start justify-between gap-4 border-b border-border px-6 py-4 last:border-b-0">
            <div className="flex-1 space-y-2">
              <Skeleton className="h-6 w-2/3" />
              <Skeleton className="h-5 w-1/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
            <Skeleton className="h-7 w-14" />
          </div>
        ))}
      </LoadingRegion>
    </Card>
  );
}
