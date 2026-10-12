import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  /** Уровень заголовка: 1 — когда состояние занимает всю страницу (404, 403). */
  headingLevel?: 1 | 2;
}

/**
 * Пустое состояние: иконка, заголовок, пояснение и действие.
 * @param props иконка, тексты и кнопка
 */
export function EmptyState({ icon: Icon, title, description, action, headingLevel = 2 }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="flex size-18 items-center justify-center rounded-full bg-surface-muted text-text-muted">
        <Icon aria-hidden="true" size={40} strokeWidth={1.5} />
      </div>
      {headingLevel === 1 ? (
        <h1 className="mt-4 text-2xl font-semibold">{title}</h1>
      ) : (
        <h2 className="mt-4 text-lg font-semibold">{title}</h2>
      )}
      {description ? <p className="mt-2 max-w-md text-text-muted">{description}</p> : null}
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}
