import { useEffect, useRef, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { FileText, Search } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { useSearchParams } from 'react-router';
import { ApiError, errorMessage } from '../../api/client';
import { api } from '../../api/endpoints';
import { Alert } from '../../components/ui/Alert';
import { ButtonLink } from '../../components/ui/ButtonLink';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { PageTitle } from '../../components/ui/PageTitle';
import { QueryErrorView } from '../../components/layout/QueryErrorView';
import {
  type FiltersFormValues,
  emptyFilters,
  filtersSchema,
  fromMatchFilters,
  toMatchFilters,
} from '../../lib/validation';
import { FiltersPanel } from './FiltersPanel';
import { ResultsList } from './ResultsList';
import { ResultsSkeleton } from './ResultsSkeleton';
import { matchKey, useCurrentMatch, useDictionaries, useStartMatching } from './api';

const MAX_PAGES = 10;

/** Главная страница соискателя: фильтры, запуск подбора, результаты с пагинацией (`/`). */
export function MatchingPage() {
  const [params, setParams] = useSearchParams();
  const rawPage = Number(params.get('page') ?? '1');
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? Math.min(rawPage, MAX_PAGES) : 1;

  const client = useQueryClient();
  const dictionaries = useDictionaries();
  const current = useCurrentMatch(page);
  const start = useStartMatching();
  const [startError, setStartError] = useState<string | null>(null);
  const [noResume, setNoResume] = useState(false);
  const form = useForm<FiltersFormValues>({ resolver: zodResolver(filtersSchema), defaultValues: emptyFilters });

  const appliedRun = useRef<string | null>(null);
  const { isDirty } = form.formState;
  useEffect(() => {
    // Фильтры подставляются из ответа один раз на каждый подбор; уже введённые пользователем значения не затираются.
    if (current.data && appliedRun.current !== current.data.run_id) {
      appliedRun.current = current.data.run_id;
      if (!isDirty) form.reset(fromMatchFilters(current.data.filters));
    }
  }, [current.data, form, isDirty]);

  const totalPages = current.data?.total_pages;
  useEffect(() => {
    if (totalPages !== undefined && page < Math.min(totalPages, MAX_PAGES)) {
      void client.prefetchQuery({ queryKey: matchKey(page + 1), queryFn: () => api.currentMatching(page + 1) });
    }
  }, [client, page, totalPages]);

  function submit(values: FiltersFormValues) {
    if (start.isPending) return;
    setStartError(null);
    setNoResume(false);
    start.mutate(toMatchFilters(values), {
      onSuccess: () => setParams({ page: '1' }),
      onError: (e) => {
        if (e instanceof ApiError && e.code === 'RESUME_NOT_FOUND') setNoResume(true);
        else if (e instanceof ApiError && e.code === 'RESUME_NOT_READY') {
          setStartError('Резюме ещё обрабатывается. Повторите подбор через несколько секунд.');
        } else setStartError(errorMessage(e));
      },
    });
  }

  function changePage(next: number) {
    setParams({ page: String(next) });
    window.scrollTo({ top: 0 });
  }

  function renderResults() {
    if (noResume) {
      return (
        <Alert
          variant="info"
          actions={<ButtonLink to="/profile">Загрузить резюме</ButtonLink>}
        >
          <span className="inline-flex items-center gap-2">
            <FileText aria-hidden="true" size={16} strokeWidth={2} />
            Для подбора вакансий загрузите резюме.
          </span>
        </Alert>
      );
    }
    if (startError) return <Alert variant="danger">{startError}</Alert>;
    if (current.isPending) return <ResultsSkeleton />;
    if (current.isError) return <QueryErrorView error={current.error} onRetry={() => void current.refetch()} />;
    if (!current.data) {
      return (
        <Card flush>
          <EmptyState icon={Search} title="Задайте фильтры и нажмите «Подобрать вакансии»" />
        </Card>
      );
    }
    return <ResultsList data={current.data} onPage={changePage} onReset={() => form.reset(emptyFilters)} />;
  }

  return (
    <>
      <PageTitle title="Подбор вакансий" />
      <div className="mt-6 flex items-start gap-6">
        <FiltersPanel
          form={form}
          dictionaries={dictionaries.data}
          loading={start.isPending}
          onSubmit={submit}
          onReset={() => form.reset(emptyFilters)}
        />
        <div className="min-w-0 flex-1">
          {dictionaries.isError ? (
            <div className="mb-4">
              <QueryErrorView error={dictionaries.error} onRetry={() => void dictionaries.refetch()} />
            </div>
          ) : null}
          {renderResults()}
        </div>
      </div>
    </>
  );
}
