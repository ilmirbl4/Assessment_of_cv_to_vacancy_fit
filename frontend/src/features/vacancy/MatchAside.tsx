import { Link } from 'react-router';
import type { VacancyDetail } from '../../api/types';
import { errorMessage } from '../../api/client';
import { Alert } from '../../components/ui/Alert';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { matchTone } from '../../components/ui/MatchBadge';
import { ProgressBar } from '../../components/ui/ProgressBar';
import { formatPercent } from '../../lib/format';
import { useAddFavorite } from './api';

const toneText = { success: 'text-success', warning: 'text-warning', neutral: 'text-text-muted' } as const;

/**
 * Правая колонка страницы вакансии: процент соответствия и кнопка избранного.
 * @param vacancy данные вакансии
 */
export function MatchAside({ vacancy }: { vacancy: VacancyDetail }) {
  const add = useAddFavorite(vacancy.id);
  const percent = vacancy.match_percent;
  const covered = vacancy.requirements.filter((r) => r.status === 'covered').length;
  const tone = percent === null ? 'neutral' : (matchTone(percent) as keyof typeof toneText);
  return (
    <Card as="div" className="sticky top-22 w-80 shrink-0 self-start">
      {percent !== null ? (
        <>
          <h2 className="text-sm font-medium text-text-muted">Соответствие резюме</h2>
          <p className={`mt-1 text-3xl font-semibold tabular ${toneText[tone]}`}>{formatPercent(percent)}</p>
          <div className="mt-3">
            <ProgressBar percent={percent} />
          </div>
          <p className="mt-2 text-sm text-text-muted">
            Покрыто {covered} из {vacancy.requirements.length}
          </p>
        </>
      ) : null}
      <div className={percent !== null ? 'mt-6' : ''}>
        {vacancy.is_favorite ? (
          <div className="flex flex-col gap-3">
            <Button disabled variant="secondary" fullWidth>
              В избранном
            </Button>
            <Link to="/favorites" className="text-center text-sm text-primary hover:underline">
              Перейти в избранное
            </Link>
          </div>
        ) : (
          <Button fullWidth loading={add.isPending} onClick={() => add.mutate()}>
            Добавить в избранное
          </Button>
        )}
        {add.isError ? (
          <Alert variant="danger" className="mt-3">
            {errorMessage(add.error)}
          </Alert>
        ) : null}
      </div>
    </Card>
  );
}
