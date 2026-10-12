import { useState } from 'react';
import { Play } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from 'recharts';
import { errorMessage } from '../../api/client';
import type { CollectionRun } from '../../api/types';
import { Alert } from '../../components/ui/Alert';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { LoadingRegion } from '../../components/ui/LoadingRegion';
import { useDocumentTitle } from '../../components/ui/PageTitle';
import { Skeleton } from '../../components/ui/Skeleton';
import { StatCard } from '../../components/ui/StatCard';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Table, Td, Th } from '../../components/ui/Table';
import { QueryErrorView } from '../../components/layout/QueryErrorView';
import { cn } from '../../lib/cn';
import { formatDateTime, formatNumber } from '../../lib/format';
import { ChartCard, axisTick, ChartLegend, shortDate, tooltipStyle } from './ChartCard';
import { isAlreadyRunning, useCollection, useStartCollection } from './api';

/** Дашборд «Сбор данных»: активные вакансии, запуск сбора, диаграмма и таблица запусков. */
export function CollectionPage() {
  useDocumentTitle('Сбор данных');
  const query = useCollection();
  const start = useStartCollection();
  const [startError, setStartError] = useState<string | null>(null);

  if (query.isPending) {
    return (
      <LoadingRegion className="flex flex-col gap-6">
        <div className="flex gap-6">
          <Skeleton className="h-28 flex-1" />
          <Skeleton className="h-28 flex-1" />
          <Skeleton className="h-28 flex-1" />
        </div>
        <Skeleton className="h-80 w-full" />
        <Skeleton className="h-64 w-full" />
      </LoadingRegion>
    );
  }
  if (query.isError) return <QueryErrorView error={query.error} onRetry={() => void query.refetch()} />;

  const { runs, is_running, active_vacancies_total } = query.data;
  const last = runs[0];
  const errorsTotal = runs.reduce((sum, r) => sum + r.error_count, 0);
  const chartData = [...runs].reverse().map((r) => ({
    date: shortDate(r.started_at.slice(0, 10)),
    new_count: r.new_count,
    updated_count: r.updated_count,
    deactivated_count: r.deactivated_count,
  }));

  function launch() {
    setStartError(null);
    start.mutate(undefined, {
      onError: (e) => setStartError(isAlreadyRunning(e) ? 'Сбор уже выполняется' : errorMessage(e)),
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-stretch gap-6">
        <StatCard label="Активных вакансий" value={formatNumber(active_vacancies_total)} />
        <StatCard
          label="Последний сбор"
          value={<span className="text-xl">{last ? formatDateTime(last.started_at) : '—'}</span>}
          note={last ? <StatusBadge kind={last.status} /> : undefined}
        />
        <StatCard label="Ошибок за 30 суток" value={formatNumber(errorsTotal)} />
        <div className="flex items-start pt-1">
          <Button icon={is_running ? undefined : Play} loading={is_running || start.isPending} onClick={launch}>
            {is_running ? 'Сбор выполняется…' : 'Запустить сбор'}
          </Button>
        </div>
      </div>
      {startError ? <Alert variant="warning">{startError}</Alert> : null}

      <ChartCard title="Запуски за 30 суток" unit="Число вакансий по запускам">
        <BarChart data={chartData}>
          <CartesianGrid vertical={false} stroke="var(--color-chart-grid)" />
          <XAxis dataKey="date" tick={axisTick} tickLine={false} minTickGap={24} />
          <YAxis tick={axisTick} tickLine={false} axisLine={false} tickFormatter={formatNumber} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => formatNumber(Number(v))} />
          <Legend verticalAlign="top" align="right" content={(props) => <ChartLegend payload={props.payload} />} />
          <Bar dataKey="new_count" name="Новых" fill="var(--color-chart-3)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="updated_count" name="Обновлено" fill="var(--color-chart-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="deactivated_count" name="Деактивировано" fill="var(--color-chart-4)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ChartCard>

      <Card as="div" flush>
        <RunsTable runs={runs} />
      </Card>
    </div>
  );
}

/**
 * Таблица запусков сбора за 30 суток; строки со статусом «Ошибка» и ненулевым числом ошибок выделены.
 * @param runs запуски, новые сверху
 */
export function RunsTable({ runs }: { runs: CollectionRun[] }) {
  return (
    <Table caption="Запуски сбора данных за последние 30 суток">
      <thead>
        <tr>
          <Th>Начало</Th>
          <Th>Окончание</Th>
          <Th>Статус</Th>
          <Th numeric>Новых</Th>
          <Th numeric>Обновлено</Th>
          <Th numeric>Деактивировано</Th>
          <Th numeric>Ошибок</Th>
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => (
          <tr
            key={r.id}
            data-highlight={r.status === 'failed' && r.error_count > 0 ? 'error' : undefined}
            className={cn(r.status === 'failed' && r.error_count > 0 && 'bg-danger-soft')}
          >
            <Td>{formatDateTime(r.started_at)}</Td>
            <Td>{r.finished_at ? formatDateTime(r.finished_at) : '—'}</Td>
            <Td>
              <StatusBadge kind={r.status} />
            </Td>
            <Td numeric>{formatNumber(r.new_count)}</Td>
            <Td numeric>{formatNumber(r.updated_count)}</Td>
            <Td numeric>{formatNumber(r.deactivated_count)}</Td>
            <Td numeric>{formatNumber(r.error_count)}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
