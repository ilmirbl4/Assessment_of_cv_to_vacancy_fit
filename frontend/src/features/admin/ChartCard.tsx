import type { ReactElement } from 'react';
import { ResponsiveContainer } from 'recharts';
import { Card } from '../../components/ui/Card';

interface ChartCardProps {
  title: string;
  /** Подпись единиц измерения под заголовком. */
  unit?: string;
  height?: 200 | 280;
  children: ReactElement;
}

/**
 * Карточка графика: заголовок h2, единицы измерения и адаптивный контейнер recharts.
 * `initialDimension` задаёт размер до первого измерения (нужно в тестовой среде без вёрстки).
 */
export function ChartCard({ title, unit, height = 280, children }: ChartCardProps) {
  return (
    <Card title={title}>
      {unit ? <p className="-mt-3 mb-3 text-sm text-text-muted">{unit}</p> : null}
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 800, height }}>
          {children}
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

export const axisTick = { fontSize: 12, fill: 'var(--color-text-muted)' };
export const tooltipStyle = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 8,
  boxShadow: 'var(--shadow-raised)',
};

/**
 * Преобразует дату ГГГГ-ММ-ДД в «ДД.ММ» для подписи оси.
 * @param iso дата
 */
export function shortDate(iso: string): string {
  const [, m, d] = iso.split('-');
  return `${d}.${m}`;
}

interface LegendEntry {
  value?: unknown;
  color?: string;
}

/**
 * Собственная легенда графика: список «цвет — название». Стандартная легенда recharts
 * добавляет англоязычные aria-label («legend icon»), поэтому используется своя разметка.
 * @param payload элементы легенды от recharts
 */
export function ChartLegend({ payload }: { payload?: readonly LegendEntry[] }) {
  return (
    <ul className="flex flex-wrap justify-end gap-4 text-sm text-text-muted">
      {(payload ?? []).map((entry) => (
        <li key={String(entry.value)} className="flex items-center gap-1.5">
          <span aria-hidden="true" className="size-3 rounded-sm" style={{ background: entry.color }} />
          {String(entry.value)}
        </li>
      ))}
    </ul>
  );
}
