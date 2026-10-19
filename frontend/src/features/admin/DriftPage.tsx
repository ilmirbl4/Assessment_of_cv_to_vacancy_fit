import { useState } from 'react';
import { Navigate, Outlet, useLocation, useOutletContext, useSearchParams } from 'react-router';
import type { DriftDashboard } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { CardTabs } from '../../components/ui/CardTabs';
import { Field } from '../../components/ui/Field';
import { Input } from '../../components/ui/Input';
import { LoadingRegion } from '../../components/ui/LoadingRegion';
import { useDocumentTitle } from '../../components/ui/PageTitle';
import { Skeleton } from '../../components/ui/Skeleton';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { QueryErrorView } from '../../components/layout/QueryErrorView';
import { formatDate, formatDecimal, formatPercent, shiftIsoDate, toIsoDate } from '../../lib/format';
import { makePeriodSchema } from '../../lib/validation';
import { AdversarialSection } from './AdversarialSection';
import { FavoriteRateSection } from './FavoriteRateSection';
import { PsiSection } from './PsiSection';
import { ScoresSection, formatPValue } from './ScoresSection';
import { favoriteRateSummary, inputsDrifted, scoresDrifted, useDrift } from './api';

interface Draft {
  from: string;
  to: string;
}

/**
 * Дашборд «Дрейф данных»: общий выбор периода и три раздела-маршрута —
 * «Входные данные» (`data`), «Выходы модели» (`model`), «Отклик пользователей» (`feedback`).
 * Карточки разделов показывают ключевые значения и состояние, данные передаются в раздел через Outlet.
 */
export function DriftPage() {
  useDocumentTitle('Дрейф данных');
  const [params, setParams] = useSearchParams();
  const from = params.get('from') ?? undefined;
  const to = params.get('to') ?? undefined;
  const query = useDrift(from, to);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [errors, setErrors] = useState<Partial<Draft>>({});
  const today = toIsoDate();

  const shown: Draft = draft ?? {
    from: from ?? query.data?.current_period.from ?? '',
    to: to ?? query.data?.current_period.to ?? '',
  };

  /** Проверяет период; запрос уходит (через изменение URL) только для корректного периода. */
  function apply(next: Draft) {
    setDraft(next);
    const result = makePeriodSchema(today).safeParse(next);
    if (!result.success) {
      const found: Partial<Draft> = {};
      for (const issue of result.error.issues) {
        const key = issue.path[0] as keyof Draft;
        found[key] ??= issue.message;
      }
      setErrors(found);
      return;
    }
    setErrors({});
    setParams({ from: next.from, to: next.to });
  }

  function preset(days: number) {
    apply({ from: shiftIsoDate(today, -(days - 1)), to: today });
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="flex items-start gap-4">
          <Field label="Начало периода" error={errors.from}>
            {(p) => <Input type="date" value={shown.from} max={today} onChange={(e) => apply({ ...shown, from: e.target.value })} {...p} />}
          </Field>
          <Field label="Конец периода" error={errors.to}>
            {(p) => <Input type="date" value={shown.to} max={today} onChange={(e) => apply({ ...shown, to: e.target.value })} {...p} />}
          </Field>
          <div className="flex gap-3 pt-7">
            <Button variant="secondary" onClick={() => preset(7)}>
              7 дней
            </Button>
            <Button variant="secondary" onClick={() => preset(30)}>
              30 дней
            </Button>
          </div>
        </div>
        {query.data ? (
          <p className="mt-3 text-sm text-text-muted">
            Эталонный период: {formatDate(query.data.reference_period.from)} – {formatDate(query.data.reference_period.to)}
          </p>
        ) : null}
      </div>

      {query.isPending ? (
        <LoadingRegion className="flex flex-col gap-6">
          <div className="grid grid-cols-3 gap-6">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-64 w-full" />
        </LoadingRegion>
      ) : query.isError ? (
        <QueryErrorView error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <>
          <DriftSections data={query.data} />
          <Outlet context={query.data} />
        </>
      )}
    </div>
  );
}

/** Карточки-разделы дашборда с ключевыми значениями; адрес раздела сохраняет выбранный период. */
function DriftSections({ data }: { data: DriftDashboard }) {
  const { search } = useLocation();
  const maxPsi = Math.max(...data.indicators.map((i) => i.psi), 0);
  const lastRoc = data.adversarial.periods.at(-1)?.roc_auc;
  const favorites = favoriteRateSummary(data);
  const p = formatPValue(data.model_scores.p_value);
  const badge = (warn: boolean) => <StatusBadge kind={warn ? 'drift' : 'ok'} />;
  return (
    <CardTabs
      label="Разделы дрейфа данных"
      items={[
        {
          to: { pathname: '/admin/drift/data', search },
          title: 'Входные данные',
          description: 'PSI вакансий и резюме, состязательная валидация',
          summary: `PSI до ${formatDecimal(maxPsi)}${lastRoc === undefined ? '' : ` · ROC-AUC ${formatDecimal(lastRoc)}`}`,
          status: badge(inputsDrifted(data)),
        },
        {
          to: { pathname: '/admin/drift/model', search },
          title: 'Выходы модели',
          description: 'Оценки кросс-энкодера, тест Колмогорова — Смирнова',
          summary: `D = ${formatDecimal(data.model_scores.statistic)} · p ${p.startsWith('<') ? p : `= ${p}`}`,
          status: badge(scoresDrifted(data)),
        },
        {
          to: { pathname: '/admin/drift/feedback', search },
          title: 'Отклик пользователей',
          description: 'Доля подборов с добавлением в избранное',
          summary:
            favorites.share === null
              ? 'Подборов за период нет'
              : `${formatPercent(favorites.share * 100)} при эталоне ${formatPercent(data.favorite_rate.reference_share * 100)}`,
          status: badge(favorites.dropped),
        },
      ]}
    />
  );
}

/** Данные дашборда, загруженные страницей `DriftPage`. */
function useDriftData() {
  return useOutletContext<DriftDashboard>();
}

/** `/admin/drift` → `/admin/drift/data` с сохранением периода. */
export function DriftIndex() {
  const { search } = useLocation();
  return <Navigate to={{ pathname: '/admin/drift/data', search }} replace />;
}

/** Раздел «Входные данные». */
export function DriftInputsView() {
  const data = useDriftData();
  return (
    <>
      <PsiSection data={data} />
      <AdversarialSection data={data} />
    </>
  );
}

/** Раздел «Выходы модели». */
export function DriftModelView() {
  return <ScoresSection data={useDriftData()} />;
}

/** Раздел «Отклик пользователей». */
export function DriftFeedbackView() {
  return <FavoriteRateSection data={useDriftData()} />;
}
