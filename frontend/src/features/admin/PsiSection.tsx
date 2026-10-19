import { AlertTriangle } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from 'recharts';
import type { DriftDashboard, DriftEntity, DriftIndicator } from '../../api/types';
import { Badge } from '../../components/ui/Badge';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Table, Td, Th } from '../../components/ui/Table';
import { cn } from '../../lib/cn';
import { formatDecimal, formatRatio } from '../../lib/format';
import { ChartCard, axisTick, ChartLegend, tooltipStyle } from './ChartCard';

export const ENTITY_LABEL: Record<DriftEntity, string> = { vacancies: 'Вакансии', resumes: 'Резюме' };
const ENTITY_SHARE: Record<DriftEntity, string> = { vacancies: 'Доля вакансий', resumes: 'Доля резюме' };

/**
 * Таблица PSI и диаграммы «эталон против текущего периода» для вакансий и резюме.
 * Строка выделяется, только если PSI строго больше порога.
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
              <Th>Данные</Th>
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
                  <Td>{ENTITY_LABEL[i.entity]}</Td>
                  <Td numeric>{formatDecimal(i.psi)}</Td>
                  <Td>
                    <StatusBadge kind={warn ? 'drift' : 'ok'} />
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </Table>
        <p className="mt-3 text-sm text-text-muted">
          Порог предупреждения: PSI &gt; {formatRatio(data.psi_threshold)}. Для эмбеддингов PSI считается по
          распределению косинусного расстояния до центроида эталонного периода.
        </p>
      </Card>

      <div className="grid grid-cols-2 gap-6">
        {data.indicators.map((i) => (
          <IndicatorChart key={i.key} indicator={i} threshold={data.psi_threshold} />
        ))}
      </div>
    </>
  );
}

/** Столбчатая диаграмма одного показателя с бейджем PSI и таблицей данных. */
function IndicatorChart({ indicator: i, threshold }: { indicator: DriftIndicator; threshold: number }) {
  const warn = i.psi > threshold;
  const rows = i.reference.map((r, idx) => ({ bin: r.bin, reference: r.share, current: i.current[idx]?.share ?? 0 }));
  return (
    <ChartCard
      title={i.name}
      unit={`${ENTITY_SHARE[i.entity]} · ${i.bins_label.toLowerCase()}`}
      height={200}
      headerAction={
        <Badge tone={warn ? 'warning' : 'neutral'} className="shrink-0 tabular">
          {warn ? <AlertTriangle aria-hidden="true" size={14} strokeWidth={2} /> : null}
          PSI {formatDecimal(i.psi)}
        </Badge>
      }
      table={
        <Table caption={`${i.name}: эталон и текущий период`}>
          <thead>
            <tr>
              <Th>{i.bins_label}</Th>
              <Th numeric>Эталон</Th>
              <Th numeric>Текущий период</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.bin}>
                <Td>{r.bin}</Td>
                <Td numeric>{formatDecimal(r.reference)}</Td>
                <Td numeric>{formatDecimal(r.current)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      }
    >
      <BarChart data={rows} barGap={2}>
        <CartesianGrid vertical={false} stroke="var(--color-chart-grid)" />
        <XAxis dataKey="bin" tick={axisTick} tickLine={false} interval={0} />
        <YAxis tick={axisTick} tickLine={false} axisLine={false} tickFormatter={(v) => formatDecimal(Number(v))} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => formatDecimal(Number(v))} />
        <Legend verticalAlign="top" align="right" content={(props) => <ChartLegend payload={props.payload} />} />
        <Bar dataKey="reference" name="Эталон" fill="var(--color-chart-reference)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
        <Bar dataKey="current" name="Текущий период" fill="var(--color-chart-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ChartCard>
  );
}
