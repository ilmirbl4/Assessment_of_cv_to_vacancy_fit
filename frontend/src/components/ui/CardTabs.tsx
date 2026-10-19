import type { ReactNode } from 'react';
import { NavLink, type To } from 'react-router';
import { cn } from '../../lib/cn';

export interface CardTabItem {
  to: To;
  title: string;
  /** Что входит в раздел. */
  description: string;
  /** Ключевые значения раздела одной строкой. */
  summary: ReactNode;
  /** Бейдж состояния раздела. */
  status: ReactNode;
}

const columns = { 2: 'grid-cols-2', 3: 'grid-cols-3', 4: 'grid-cols-4' } as const;

/**
 * Вкладки-карточки второго уровня: каждая — ссылка на маршрут со сводкой и состоянием раздела,
 * поэтому ряд карточек одновременно служит обзором. Активная помечена aria-current и рамкой primary.
 * @param items разделы (2–4)
 * @param label подпись навигации для скринридеров
 */
export function CardTabs({ items, label }: { items: CardTabItem[]; label: string }) {
  return (
    <nav aria-label={label}>
      <ul className={cn('grid gap-6', columns[items.length as keyof typeof columns] ?? 'grid-cols-3')}>
        {items.map((item) => (
          <li key={item.title}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex h-full flex-col gap-2 rounded-lg border bg-surface px-6 py-4 shadow-card',
                  isActive ? 'border-primary ring-1 ring-primary' : 'border-border hover:border-border-strong',
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span className={cn('text-lg font-semibold', isActive && 'text-primary')}>{item.title}</span>
                  <span className="flex">{item.status}</span>
                  <span className="text-sm text-text-muted">{item.description}</span>
                  <span className="mt-auto text-sm font-medium tabular">{item.summary}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
