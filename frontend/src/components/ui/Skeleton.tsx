import { cn } from '../../lib/cn';

/**
 * Блок-заглушка загрузки; форму задают классы размера.
 * @param className классы ширины и высоты
 */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn('animate-pulse rounded-md bg-surface-muted', className)} />;
}
