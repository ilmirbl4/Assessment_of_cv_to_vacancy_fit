import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { Button } from '../../components/ui/Button';
import { Field } from '../../components/ui/Field';
import { Input } from '../../components/ui/Input';
import { LoadingRegion } from '../../components/ui/LoadingRegion';
import { useDocumentTitle } from '../../components/ui/PageTitle';
import { Skeleton } from '../../components/ui/Skeleton';
import { QueryErrorView } from '../../components/layout/QueryErrorView';
import { formatDate, shiftIsoDate, toIsoDate } from '../../lib/format';
import { makePeriodSchema } from '../../lib/validation';
import { AdversarialSection } from './AdversarialSection';
import { PsiSection } from './PsiSection';
import { useDrift } from './api';

interface Draft {
  from: string;
  to: string;
}

/** Дашборд «Дрейф данных»: выбор периода, PSI, графики и состязательная валидация. */
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
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-64 w-full" />
        </LoadingRegion>
      ) : query.isError ? (
        <QueryErrorView error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <>
          <PsiSection data={query.data} />
          <AdversarialSection data={query.data} />
        </>
      )}
    </div>
  );
}
