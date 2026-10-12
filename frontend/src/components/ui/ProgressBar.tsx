import { matchTone } from './MatchBadge';

const fills = { success: 'bg-success', warning: 'bg-warning', neutral: 'bg-text-muted', danger: 'bg-danger', primary: 'bg-primary', inactive: 'bg-inactive-text' };

/**
 * Индикатор соответствия высотой 8px; цвет по шкале MatchBadge.
 * @param percent целый процент 0..100
 */
export function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-surface-muted" aria-hidden="true">
      <div className={`h-full rounded-full ${fills[matchTone(percent)]}`} style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
    </div>
  );
}
