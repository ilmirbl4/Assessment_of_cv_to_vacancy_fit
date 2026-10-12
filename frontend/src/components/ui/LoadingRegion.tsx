import type { ReactNode } from 'react';

/**
 * Область загрузки: скелетоны для зрячих и текст «Загрузка…» для скринридера.
 * @param children скелетоны
 */
export function LoadingRegion({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div role="status" aria-busy="true" className={className}>
      <span className="sr-only">Загрузка…</span>
      {children}
    </div>
  );
}
