import { NavLink } from 'react-router';
import { cn } from '../../lib/cn';

export interface TabItem {
  to: string;
  label: string;
  /** Показать индикатор-точку предупреждения. */
  warning?: boolean;
}

/**
 * Вкладки-маршруты админки: каждая вкладка — ссылка, активная помечена aria-current.
 * @param items вкладки
 * @param label подпись навигации для скринридеров
 */
export function Tabs({ items, label }: { items: TabItem[]; label: string }) {
  return (
    <nav aria-label={label} className="flex gap-6 border-b border-border">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            cn(
              '-mb-px inline-flex items-center gap-2 border-b-2 py-3 text-base font-medium',
              isActive ? 'border-primary text-primary' : 'border-transparent text-text-muted hover:text-text',
            )
          }
        >
          {item.label}
          {item.warning ? (
            <>
              <span aria-hidden="true" className="size-2 rounded-full bg-warning" />
              <span className="sr-only">есть предупреждение</span>
            </>
          ) : null}
        </NavLink>
      ))}
    </nav>
  );
}
