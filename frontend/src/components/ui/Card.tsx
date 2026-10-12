import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

interface CardProps {
  /** Заголовок секции (h2). */
  title?: ReactNode;
  /** Элемент справа от заголовка. */
  headerAction?: ReactNode;
  className?: string;
  children?: ReactNode;
  as?: 'section' | 'div';
  /** Без внутренних отступов (для списков и таблиц на всю ширину карточки). */
  flush?: boolean;
}

/**
 * Панель: белый фон, рамка, скругление и тень.
 * @param props заголовок, содержимое
 */
export function Card({ title, headerAction, className, children, as: Tag = 'section', flush = false }: CardProps) {
  return (
    <Tag className={cn('rounded-lg border border-border bg-surface shadow-card', !flush && 'p-6', className)}>
      {title ? (
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="text-xl font-semibold">{title}</h2>
          {headerAction}
        </div>
      ) : null}
      {children}
    </Tag>
  );
}
