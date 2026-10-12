import { formatPercent } from '../../lib/format';
import { Badge, type BadgeTone } from './Badge';

/**
 * Возвращает тон по шкале соответствия: ≥70 — успех, 40–69 — предупреждение, иначе нейтральный.
 * @param percent процент соответствия
 */
export function matchTone(percent: number): BadgeTone {
  if (percent >= 70) return 'success';
  if (percent >= 40) return 'warning';
  return 'neutral';
}

/**
 * Бейдж «Соответствие NN%» с цветом по шкале.
 * @param percent целый процент соответствия 0..100
 */
export function MatchBadge({ percent }: { percent: number }) {
  const text = formatPercent(percent);
  return (
    <Badge tone={matchTone(percent)} aria-label={`Соответствие ${text}`} className="font-semibold tabular">
      {text}
    </Badge>
  );
}
