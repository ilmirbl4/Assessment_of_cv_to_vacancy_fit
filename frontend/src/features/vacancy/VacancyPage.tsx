import { ArrowLeft, ExternalLink, FileText, SearchX } from 'lucide-react';
import { Link, useLocation, useParams } from 'react-router';
import { ApiError } from '../../api/client';
import { Alert } from '../../components/ui/Alert';
import { ButtonLink } from '../../components/ui/ButtonLink';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { LoadingRegion } from '../../components/ui/LoadingRegion';
import { PageTitle, useDocumentTitle } from '../../components/ui/PageTitle';
import { Skeleton } from '../../components/ui/Skeleton';
import { QueryErrorView } from '../../components/layout/QueryErrorView';
import { formatDate, formatSalary } from '../../lib/format';
import { MatchAside } from './MatchAside';
import { RequirementsTable } from './RequirementsTable';
import { useVacancy } from './api';

/** Страница вакансии (`/vacancies/:id`): сведения, требования и их покрытие, избранное. */
export function VacancyPage() {
  const { id = '' } = useParams();
  const location = useLocation();
  const query = useVacancy(id);
  const page = (location.state as { page?: number } | null)?.page;
  const backTo = page && page > 1 ? `/?page=${page}` : '/';
  useDocumentTitle('Вакансия');

  const back = (
    <Link to={backTo} className="mb-4 inline-flex items-center gap-1 text-primary hover:underline">
      <ArrowLeft aria-hidden="true" size={16} strokeWidth={2} />К результатам подбора
    </Link>
  );

  if (query.isPending) {
    return (
      <>
        {back}
        <LoadingRegion className="flex items-start gap-6">
          <div className="flex-1 space-y-6">
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
          <Skeleton className="h-56 w-80" />
        </LoadingRegion>
      </>
    );
  }
  if (query.isError) {
    if (query.error instanceof ApiError && query.error.status === 404) {
      return (
        <Card>
          <EmptyState
            icon={SearchX}
            title="Вакансия не найдена"
            headingLevel={1}
            action={<ButtonLink to="/">К результатам подбора</ButtonLink>}
          />
        </Card>
      );
    }
    return (
      <>
        {back}
        <QueryErrorView error={query.error} onRetry={() => void query.refetch()} />
      </>
    );
  }

  const v = query.data;
  return (
    <>
      {back}
      <div className="flex items-start gap-6">
        <div className="flex min-w-0 flex-1 flex-col gap-6">
          <Card as="div">
            <PageTitle title={v.title} className="text-2xl font-semibold" userContent />
            <p className="mt-2 text-lg font-medium">{formatSalary(v.salary_from, v.salary_to)}</p>
            <p className="mt-1 text-text-muted">
              <span data-user-content>{v.employer_name}</span> · <span data-user-content>{v.region_name}</span> ·
              Опубликовано {formatDate(v.published_at)}
            </p>
            <a
              href={v.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1 text-primary hover:underline"
            >
              Открыть на портале «Работа России»
              <ExternalLink aria-hidden="true" size={16} strokeWidth={2} />
            </a>
            {!v.is_active ? (
              <Alert variant="warning" className="mt-4">
                Вакансия снята с публикации и не участвует в подборе
              </Alert>
            ) : null}
          </Card>

          {v.match_percent === null ? (
            <Alert
              variant="info"
              actions={<ButtonLink to="/profile">Загрузить резюме</ButtonLink>}
            >
              <span className="inline-flex items-center gap-2">
                <FileText aria-hidden="true" size={16} strokeWidth={2} />
                Загрузите резюме, чтобы увидеть, какие требования вы покрываете
              </span>
            </Alert>
          ) : (
            <RequirementsTable requirements={v.requirements} />
          )}

          <Card title="Сведения о вакансии">
            <dl className="grid grid-cols-[12.5rem_1fr] gap-x-6 gap-y-4">
              {v.source_fields.map((f, i) => (
                <div key={`${f.label}-${i}`} className="contents">
                  <dt data-user-content className="text-text-muted">
                    {f.label}
                  </dt>
                  <dd data-user-content className="whitespace-pre-line">
                    {f.value}
                  </dd>
                </div>
              ))}
            </dl>
          </Card>
        </div>
        <MatchAside vacancy={v} />
      </div>
    </>
  );
}
