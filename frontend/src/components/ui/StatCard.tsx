import type { ReactNode } from 'react';
import { Card } from './Card';

/**
 * Карточка с крупным числом.
 * @param label подпись
 * @param value значение
 * @param note вторичная строка
 */
export function StatCard({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <Card as="div" className="flex-1">
      <p className="text-sm text-text-muted">{label}</p>
      <p className="mt-1 text-3xl font-semibold tabular">{value}</p>
      {note ? <div className="mt-1 text-sm text-text-muted">{note}</div> : null}
    </Card>
  );
}
