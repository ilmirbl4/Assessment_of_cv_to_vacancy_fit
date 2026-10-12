import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts';
import type { SpeedDay } from '../../api/types';
import { Card } from '../../components/ui/Card';
import { LoadingRegion } from '../../components/ui/LoadingRegion';
import { useDocumentTitle } from '../../components/ui/PageTitle';
import { Skeleton } from '../../components/ui/Skeleton';
import { StatCard } from '../../components/ui/StatCard';
import { Table, Td, Th } from '../../components/ui/Table';
import { QueryErrorView } from '../../components/layout/QueryErrorView';
import { formatDate, formatNumber } from '../../lib/format';
import { ChartCard, axisTick, ChartLegend, shortDate, tooltipStyle } from './ChartCard';
import { useSpeed } from './api';

const NORM_MS = 1000;

/** Сводные значения за период: средневзвешенные по числу подборов. */
function summarize(days: SpeedDay[]) {
  const count = days.reduce((s, d) => s + d.count, 0);
  const weighted = (pick: (d: SpeedDay) => number) =>
    count === 0 ? 0 : days.reduce((s, d) => s + pick(d) * d.count, 0) / count;
  return { count, avg: weighted((d) => d.avg_ms), p95: weighted((d) => d.p95_ms) };
}

/** Дашборд «Скорость подбора»: графики времени и числа подборов, сводка и таблица по дням. */
export function SpeedPage() {
  useDocumentTitle('Скорость подбора');
  const query = useSpeed();

  if (query.isPending) {
    return (
      <LoadingRegion className="flex flex-col gap-6">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-80 w-full" />
        <Skeleton className="h-80 w-full" />
      </LoadingRegion>
    );
  }
  if (query.isError) return <QueryErrorView error={query.error} onRetry={() => void query.refetch()} />;

  const days = query.data.days;
  const total = summarize(days);
  const data = days.map((d) => ({ ...d, label: shortDate(d.date) }));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex gap-6">
        <StatCard label="Среднее время за 30 суток, мс" value={formatNumber(total.avg)} />
        <StatCard label="95-й перцентиль за 30 суток, мс" value={formatNumber(total.p95)} />
        <StatCard label="Подборов за 30 суток" value={formatNumber(total.count)} />
      </div>

      <ChartCard title="Время подбора, мс" unit="Среднее и 95-й перцентиль по суткам">
        <LineChart data={data}>
          <CartesianGrid vertical={false} stroke="var(--color-chart-grid)" />
          <XAxis dataKey="label" tick={axisTick} tickLine={false} minTickGap={24} />
          <YAxis tick={axisTick} tickLine={false} axisLine={false} domain={[0, 1200]} tickFormatter={formatNumber} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${formatNumber(Number(v))} мс`} />
          <Legend verticalAlign="top" align="right" content={(props) => <ChartLegend payload={props.payload} />} />
          <ReferenceLine
            y={NORM_MS}
            stroke="var(--color-chart-threshold)"
            strokeDasharray="6 4"
            label={{ value: 'Норматив ТЗ: 1 с', position: 'insideTopLeft', fill: 'var(--color-chart-threshold)', fontSize: 12 }}
          />
          <Line type="monotone" dataKey="avg_ms" name="Среднее время, мс" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="p95_ms" name="95-й перцентиль, мс" stroke="var(--color-chart-2)" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ChartCard>

      <ChartCard title="Число подборов" unit="Подборов по суткам">
        <BarChart data={data}>
          <CartesianGrid vertical={false} stroke="var(--color-chart-grid)" />
          <XAxis dataKey="label" tick={axisTick} tickLine={false} minTickGap={24} />
          <YAxis tick={axisTick} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey="count" name="Подборов" fill="var(--color-chart-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ChartCard>

      <Card as="div" flush>
        <Table caption="Скорость подбора по суткам">
          <thead>
            <tr>
              <Th>Дата</Th>
              <Th numeric>Среднее, мс</Th>
              <Th numeric>95-й перцентиль, мс</Th>
              <Th numeric>Подборов</Th>
            </tr>
          </thead>
          <tbody>
            {days.map((d) => (
              <tr key={d.date}>
                <Td>{formatDate(d.date)}</Td>
                <Td numeric>{formatNumber(d.avg_ms)}</Td>
                <Td numeric>{formatNumber(d.p95_ms)}</Td>
                <Td numeric>{formatNumber(d.count)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
    </div>
  );
}
