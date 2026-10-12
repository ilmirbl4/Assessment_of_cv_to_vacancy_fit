import { SearchX } from 'lucide-react';
import type { MatchPage } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { Pagination } from '../../components/ui/Pagination';
import { VacancyCardItem } from './VacancyCardItem';

interface ResultsListProps {
  data: MatchPage;
  onPage: (page: number) => void;
  onReset: () => void;
}

/** Результаты подбора: счётчик, карточки в порядке сервера, пагинация или пустое состояние. */
export function ResultsList({ data, onPage, onReset }: ResultsListProps) {
  if (data.total === 0) {
    return (
      <Card flush>
        <EmptyState
          icon={SearchX}
          title="Ничего не найдено"
          description="По заданным фильтрам подходящих вакансий не найдено. Попробуйте ослабить фильтры: выбрать другой регион, снизить минимальную зарплату или снять отметку «Только с указанной зарплатой»."
          action={
            <Button variant="secondary" onClick={onReset}>
              Сбросить фильтры
            </Button>
          }
        />
      </Card>
    );
  }
  return (
    <Card flush>
      <p aria-live="polite" className="border-b border-border px-6 py-4 font-medium">
        Найдено вакансий: <span className="tabular">{data.total}</span>
        {data.total === 100 ? ' (показаны 100 наиболее подходящих)' : ''}
      </p>
      <ul>
        {data.items.map((v) => (
          <VacancyCardItem key={v.id} vacancy={v} page={data.page} />
        ))}
      </ul>
      <div className="border-t border-border px-6 py-4">
        <Pagination page={data.page} totalPages={Math.min(data.total_pages, 10)} onChange={onPage} />
      </div>
    </Card>
  );
}
