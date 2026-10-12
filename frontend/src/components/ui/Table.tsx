import type { ComponentProps, ReactNode } from 'react';
import { cn } from '../../lib/cn';

/**
 * Таблица дизайн-системы с обязательной подписью (caption скрыт визуально).
 * @param caption подпись таблицы для скринридеров
 * @param children thead/tbody
 */
export function Table({ caption, children, className }: { caption: string; children: ReactNode; className?: string }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <table className={cn('w-full border-collapse text-sm', className)}>
        <caption className="sr-only">{caption}</caption>
        {children}
      </table>
    </div>
  );
}

/** Ячейка заголовка столбца (`scope="col"`); `numeric` выравнивает по правому краю. */
export function Th({ numeric, className, ...rest }: ComponentProps<'th'> & { numeric?: boolean }) {
  return (
    <th
      scope="col"
      className={cn(
        'bg-surface-muted px-4 py-3 text-sm font-medium text-text-muted',
        numeric ? 'text-right' : 'text-left',
        className,
      )}
      {...rest}
    />
  );
}

/** Ячейка данных; `numeric` выравнивает по правому краю и включает табличные цифры. */
export function Td({ numeric, className, ...rest }: ComponentProps<'td'> & { numeric?: boolean }) {
  return (
    <td
      className={cn('min-h-11 border-t border-border px-4 py-3 align-top', numeric && 'tabular text-right', className)}
      {...rest}
    />
  );
}
