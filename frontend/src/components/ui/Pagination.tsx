import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '../../lib/cn';

/**
 * Строит список видимых элементов пагинации (до 7), «…» обозначает пропуск.
 * @param page текущая страница
 * @param total число страниц
 */
export function pageItems(page: number, total: number): (number | '…')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (page <= 4) return [1, 2, 3, 4, 5, '…', total];
  if (page >= total - 3) return [1, '…', total - 4, total - 3, total - 2, total - 1, total];
  return [1, '…', page - 1, page, page + 1, '…', total];
}

const itemClasses =
  'inline-flex h-10 min-w-10 items-center justify-center gap-1 rounded-md px-3 text-base font-medium';

/**
 * Постраничная навигация: «Назад», номера, «Вперёд».
 * @param page текущая страница (с 1)
 * @param totalPages число страниц
 * @param onChange вызывается с номером выбранной страницы
 */
export function Pagination({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <nav aria-label="Страницы результатов" className="flex flex-wrap items-center justify-center gap-1">
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
        className={cn(itemClasses, 'text-text hover:bg-surface-muted disabled:cursor-not-allowed disabled:text-text-disabled disabled:hover:bg-transparent')}
      >
        <ChevronLeft aria-hidden="true" size={16} strokeWidth={2} />
        Назад
      </button>
      {pageItems(page, totalPages).map((item, index) =>
        item === '…' ? (
          <span key={`gap-${index}`} aria-hidden="true" className="px-1 text-text-muted">
            …
          </span>
        ) : (
          <button
            key={item}
            type="button"
            aria-label={`Страница ${item}`}
            aria-current={item === page ? 'page' : undefined}
            onClick={() => onChange(item)}
            className={cn(
              itemClasses,
              'tabular',
              item === page ? 'bg-primary text-on-primary' : 'text-text hover:bg-surface-muted',
            )}
          >
            {item}
          </button>
        ),
      )}
      <button
        type="button"
        disabled={page >= totalPages}
        onClick={() => onChange(page + 1)}
        className={cn(itemClasses, 'text-text hover:bg-surface-muted disabled:cursor-not-allowed disabled:text-text-disabled disabled:hover:bg-transparent')}
      >
        Вперёд
        <ChevronRight aria-hidden="true" size={16} strokeWidth={2} />
      </button>
    </nav>
  );
}
