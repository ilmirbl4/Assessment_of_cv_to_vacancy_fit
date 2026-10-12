import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

/**
 * Контейнер контента: максимум 1200px по центру, поля 24px, отступ сверху 32px.
 * @param narrow ограничить ширину колонки 800px (кабинет, избранное)
 */
export function PageContainer({ children, narrow = false }: { children: ReactNode; narrow?: boolean }) {
  return (
    <main className="mx-auto w-full max-w-page px-6 pb-12 pt-8">
      <div className={cn(narrow && 'max-w-200')}>{children}</div>
    </main>
  );
}
