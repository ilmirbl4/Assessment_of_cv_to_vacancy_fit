import { Link } from 'react-router';
import type { VacancyCard } from '../../api/types';
import { MatchBadge } from '../../components/ui/MatchBadge';
import { formatDate, formatSalary } from '../../lib/format';

/**
 * Строка вакансии в списке результатов: название-ссылка, зарплата, работодатель, дата, процент.
 * Вся строка кликабельна через растянутый псевдоэлемент ссылки.
 * @param vacancy карточка вакансии
 * @param page номер страницы результатов (передаётся в location.state для возврата)
 */
export function VacancyCardItem({ vacancy, page }: { vacancy: VacancyCard; page: number }) {
  return (
    <li className="relative flex items-start justify-between gap-4 border-b border-border px-6 py-4 last:border-b-0 hover:bg-surface-muted">
      <div className="min-w-0">
        <h3 className="text-lg font-semibold">
          <Link
            to={`/vacancies/${vacancy.id}`}
            state={{ page }}
            title={vacancy.title}
            data-user-content
            className="line-clamp-2 text-primary after:absolute after:inset-0 hover:underline"
          >
            {vacancy.title}
          </Link>
        </h3>
        <p className="mt-1 font-medium">{formatSalary(vacancy.salary_from, vacancy.salary_to)}</p>
        <p className="mt-1 text-sm text-text-muted">
          <span data-user-content>{vacancy.employer_name}</span> · Опубликовано {formatDate(vacancy.published_at)}
        </p>
      </div>
      <MatchBadge percent={vacancy.match_percent} />
    </li>
  );
}
