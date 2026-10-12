import { Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from 'recharts';
import type { DriftDashboard } from '../../api/types';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Table, Td, Th } from '../../components/ui/Table';
import { cn } from '../../lib/cn';
import { formatDecimal, formatRatio } from '../../lib/format';
import { ChartCard, axisTick, ChartLegend, tooltipStyle } from './ChartCard';

/**
 * Таблица PSI и диаграммы «эталон против текущего периода». Строка выделяется, только если PSI строго больше порога.
 * @param data данные дашборда дрейфа
 */
export function PsiSection({ data }: { data: DriftDashboard }) {
  return (
    <>
      <Card title="Индекс стабильности популяции (PSI)">
        <Table caption="PSI по показателям">
          <thead>
            <tr>
              <Th>Показатель</Th>
              <Th numeric>PSI</Th>
              <Th>Состояние</Th>
            </tr>
          </thead>
          <tbody>
            {data.indicators.map((i) => {
              const warn = i.psi > data.psi_threshold;
              return (
                <tr key={i.key} data-drift={warn ? 'warning' : 'ok'} className={cn(warn && 'bg-warning-soft')}>
                  <Td>{i.name}</Td>
                  <Td numeric>{formatDecimal(i.psi)}</Td>
                  <Td>
                    <StatusBadge kind={warn ? 'drift' : 'ok'} />
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </Table>
        <p className="mt-3 text-sm text-text-muted">Порог предупреждения: PSI &gt; {formatRatio(data.psi_threshold)}</p>
      </Card>

      <div className="grid grid-cols-3 gap-6">
        {data.indicators.map((i) => {
          const rows = i.reference.map((r, idx) => ({
            bin: r.bin,
            reference: r.share,
            current: i.current[idx]?.share ?? 0,
          }));
          return (
            <ChartCard key={i.key} title={i.name} unit="Доля вакансий" height={200}>
              <BarChart data={rows}>
                <CartesianGrid vertical={false} stroke="var(--color-chart-grid)" />
                <XAxis
                  dataKey="bin"
                  tick={axisTick}
                  tickLine={false}
                  interval={0}
                  angle={rows.length > 5 ? -35 : 0}
                  textAnchor={rows.length > 5 ? 'end' : 'middle'}
                  height={rows.length > 5 ? 56 : 30}
                />
                <YAxis tick={axisTick} tickLine={false} axisLine={false} tickFormatter={(v) => formatDecimal(Number(v))} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => formatDecimal(Number(v))} />
                <Legend verticalAlign="top" align="right" content={(props) => <ChartLegend payload={props.payload} />} />
                <Bar dataKey="reference" name="Эталон" fill="var(--color-chart-reference)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                <Bar dataKey="current" name="Текущий период" fill="var(--color-chart-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ChartCard>
          );
        })}
      </div>
    </>
  );
}
