import { Link } from 'react-router';
import type { FavoriteItem } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { cn } from '../../lib/cn';
import { formatDate, formatSalary } from '../../lib/format';

interface FavoriteRowProps {
  item: FavoriteItem;
  removing: boolean;
  onRemove: () => void;
}

/**
 * Строка избранной вакансии. Снятая с публикации вакансия серая и с бейджем «Снята с публикации».
 */
export function FavoriteRow({ item, removing, onRemove }: FavoriteRowProps) {
  const { vacancy } = item;
  return (
    <li
      data-inactive={item.is_active ? undefined : 'true'}
      className={cn(
        'flex items-start justify-between gap-4 border-b border-border px-6 py-4 last:border-b-0',
        item.is_active ? 'bg-surface' : 'bg-inactive-bg text-inactive-text',
      )}
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">
            <Link
              to={`/vacancies/${vacancy.id}`}
              title={vacancy.title}
              data-user-content
              className={cn('line-clamp-2 hover:underline', item.is_active ? 'text-primary' : 'text-inactive-text underline')}
            >
              {vacancy.title}
            </Link>
          </h2>
          {item.is_active ? null : <StatusBadge kind="inactive" />}
        </div>
        <p className={cn('mt-1', item.is_active ? 'text-text-muted' : '')}>
          {formatSalary(vacancy.salary_from, vacancy.salary_to)} · <span data-user-content>{vacancy.employer_name}</span> ·
          Опубликовано {formatDate(vacancy.published_at)}
        </p>
      </div>
      <Button variant="secondary" size="sm" loading={removing} onClick={onRemove} className="shrink-0">
        Удалить из избранного
      </Button>
    </li>
  );
}
