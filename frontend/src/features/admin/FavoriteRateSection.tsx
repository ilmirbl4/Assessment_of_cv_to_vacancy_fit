import { CartesianGrid, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts';
import type { DriftDashboard } from '../../api/types';
import { Alert } from '../../components/ui/Alert';
import { StatCard } from '../../components/ui/StatCard';
import { Table, Td, Th } from '../../components/ui/Table';
import { formatDate, formatNumber, formatPercent } from '../../lib/format';
import { ChartCard, axisTick, shortDate, tooltipStyle } from './ChartCard';
import { favoriteRateSummary } from './api';

const NBSP = ' ';

/**
 * Форматирует разницу долей в процентных пунктах со знаком: «−4,5 п. п.», «+1 п. п.».
 * @param delta разница долей (0.045 = 4,5 п. п.)
 * @param signed выводить ли знак
 */
export function formatPoints(delta: number, signed = true): string {
  const value = Math.abs(delta * 100).toLocaleString('ru-RU', { maximumFractionDigits: 1 });
  const sign = !signed || value === '0' ? '' : delta < 0 ? '−' : '+';
  return `${sign}${value}${NBSP}п.${NBSP}п.`;
}

/**
 * Раздел «Отклик пользователей»: доля подборов, после которых соискатель добавил хотя бы одну вакансию
 * в избранное, по суткам — с уровнем эталонного периода и порогом допустимого снижения.
 * @param data данные дашборда дрейфа
 */
export function FavoriteRateSection({ data }: { data: DriftDashboard }) {
  const { reference_share, max_drop, days } = data.favorite_rate;
  const summary = favoriteRateSummary(data);
  const threshold = reference_share - max_drop;
  const points = days.map((d) => ({ label: shortDate(d.date), share: Math.round(d.share * 1000) / 10 }));
  const pct = (share: number) => formatPercent(share * 100);

  return (
    <div className="flex flex-col gap-6">
      {summary.dropped && summary.share !== null ? (
        <Alert variant="warning">
          Доля подборов с добавлением в избранное снизилась до {pct(summary.share)} при эталоне {pct(reference_share)}:
          снижение больше допустимого ({formatPoints(max_drop, false)}). Рекомендации стали реже устраивать соискателей.
        </Alert>
      ) : null}

      <div className="flex gap-6">
        <StatCard
          label="Текущий период"
          value={summary.share === null ? '—' : pct(summary.share)}
          note={`${formatNumber(summary.withFavorite)} из ${formatNumber(summary.runs)} подборов`}
        />
        <StatCard
          label="Эталонный период"
          value={pct(reference_share)}
          note={`${formatDate(data.reference_period.from)} – ${formatDate(data.reference_period.to)}`}
        />
        <StatCard
          label="Изменение"
          value={summary.change === null ? '—' : formatPoints(summary.change)}
          note={`Допустимое снижение — ${formatPoints(max_drop, false)}`}
        />
      </div>

      <ChartCard
        title="Доля подборов с добавлением в избранное"
        unit="По суткам, %: подбор учитывается, если после него хотя бы одна вакансия добавлена в избранное"
        table={
          <Table caption="Доля подборов с добавлением в избранное по суткам">
            <thead>
              <tr>
                <Th>Дата</Th>
                <Th numeric>Подборов</Th>
                <Th numeric>С добавлением в избранное</Th>
                <Th numeric>Доля</Th>
              </tr>
            </thead>
            <tbody>
              {days.map((d) => (
                <tr key={d.date}>
                  <Td>{formatDate(d.date)}</Td>
                  <Td numeric>{formatNumber(d.runs)}</Td>
                  <Td numeric>{formatNumber(d.runs_with_favorite)}</Td>
                  <Td numeric>{pct(d.share)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        }
      >
        <LineChart data={points} margin={{ top: 8, right: 96, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--color-chart-grid)" />
          <XAxis dataKey="label" tick={axisTick} tickLine={false} minTickGap={24} />
          <YAxis tick={axisTick} tickLine={false} axisLine={false} domain={[0, 40]} ticks={[0, 10, 20, 30, 40]} tickFormatter={(v) => `${v}%`} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => formatPercent(Number(v))} />
          <ReferenceLine
            y={reference_share * 100}
            stroke="var(--color-chart-reference)"
            strokeDasharray="6 4"
            label={{ value: `Эталон ${pct(reference_share)}`, position: 'right', fill: 'var(--color-text-muted)', fontSize: 12 }}
          />
          <ReferenceLine
            y={threshold * 100}
            stroke="var(--color-chart-threshold)"
            strokeDasharray="6 4"
            label={{ value: `Порог ${pct(threshold)}`, position: 'right', fill: 'var(--color-chart-threshold)', fontSize: 12 }}
          />
          <Line type="monotone" dataKey="share" name="Доля подборов" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ChartCard>
    </div>
  );
}
