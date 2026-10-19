import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts';
import type { DriftDashboard } from '../../api/types';
import { Alert } from '../../components/ui/Alert';
import { StatCard } from '../../components/ui/StatCard';
import { Table, Td, Th } from '../../components/ui/Table';
import { formatDecimal, formatNumber, formatRatio } from '../../lib/format';
import { ChartCard, axisTick, ChartLegend, tooltipStyle } from './ChartCard';
import { scoresDrifted } from './api';

/**
 * Форматирует p-значение: очень малые значения — «< 0,001», остальные — три знака после запятой.
 * @param p p-значение
 */
export function formatPValue(p: number): string {
  if (p < 0.001) return '< 0,001';
  return p.toLocaleString('ru-RU', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}

/**
 * Накопленные доли по гистограмме: точка на правой границе каждой корзины, плюс начало отрезка (0; 0).
 * @param data данные дашборда
 */
export function cumulative(data: DriftDashboard) {
  const { reference, current } = data.model_scores;
  const step = 1 / reference.length;
  let ref = 0;
  let cur = 0;
  const points = [{ score: 0, reference: 0, current: 0 }];
  reference.forEach((r, i) => {
    ref += r.share;
    cur += current[i]?.share ?? 0;
    points.push({ score: Math.round((i + 1) * step * 100) / 100, reference: Math.round(ref * 1000) / 1000, current: Math.round(cur * 1000) / 1000 });
  });
  return points;
}

/**
 * Раздел «Выходы модели»: двухвыборочный тест Колмогорова — Смирнова для оценок кросс-энкодера,
 * гистограмма оценок и накопленные функции распределения с отметкой наибольшего разрыва.
 * @param data данные дашборда дрейфа
 */
export function ScoresSection({ data }: { data: DriftDashboard }) {
  const s = data.model_scores;
  const drifted = scoresDrifted(data);
  const histogram = s.reference.map((r, i) => ({ bin: r.bin, reference: r.share, current: s.current[i]?.share ?? 0 }));
  const cdf = cumulative(data);
  const gap = cdf.reduce((best, p) => (Math.abs(p.reference - p.current) > Math.abs(best.reference - best.current) ? p : best));

  return (
    <div className="flex flex-col gap-6">
      {drifted ? (
        <Alert variant="warning">
          Тест Колмогорова — Смирнова: D = {formatDecimal(s.statistic)}, p-значение {formatPValue(s.p_value)} меньше уровня
          значимости {formatRatio(s.alpha)} — распределение оценок кросс-энкодера в текущем периоде отличается от эталонного
        </Alert>
      ) : null}

      <div className="flex gap-6">
        <StatCard label="Статистика D" value={formatDecimal(s.statistic)} note="Наибольший разрыв функций распределения" />
        <StatCard label="p-значение" value={formatPValue(s.p_value)} note={`Уровень значимости ${formatRatio(s.alpha)}`} />
        <StatCard
          label="Размер выборок"
          value={`${formatNumber(s.reference_size)} / ${formatNumber(s.current_size)}`}
          note="Пар «требование — резюме»: эталон / текущий период"
        />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <ChartCard
          title="Распределение оценок"
          unit="Доля пар «требование — резюме» по оценке кросс-энкодера"
          table={
            <Table caption="Распределение оценок кросс-энкодера">
              <thead>
                <tr>
                  <Th>Оценка</Th>
                  <Th numeric>Эталон</Th>
                  <Th numeric>Текущий период</Th>
                </tr>
              </thead>
              <tbody>
                {histogram.map((r) => (
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
          <BarChart data={histogram} barGap={2}>
            <CartesianGrid vertical={false} stroke="var(--color-chart-grid)" />
            <XAxis dataKey="bin" tick={axisTick} tickLine={false} interval={1} />
            <YAxis tick={axisTick} tickLine={false} axisLine={false} tickFormatter={(v) => formatDecimal(Number(v))} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => formatDecimal(Number(v))} />
            <Legend verticalAlign="top" align="right" content={(props) => <ChartLegend payload={props.payload} />} />
            <Bar dataKey="reference" name="Эталон" fill="var(--color-chart-reference)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="current" name="Текущий период" fill="var(--color-chart-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ChartCard>

        <ChartCard
          title="Функции распределения"
          unit="Накопленная доля пар; пунктир — место наибольшего разрыва"
          table={
            <Table caption="Накопленные функции распределения оценок">
              <thead>
                <tr>
                  <Th>Оценка не выше</Th>
                  <Th numeric>Эталон</Th>
                  <Th numeric>Текущий период</Th>
                  <Th numeric>Разрыв</Th>
                </tr>
              </thead>
              <tbody>
                {cdf.slice(1).map((p) => (
                  <tr key={p.score}>
                    <Td className="tabular">{formatRatio(p.score)}</Td>
                    <Td numeric>{formatDecimal(p.reference)}</Td>
                    <Td numeric>{formatDecimal(p.current)}</Td>
                    <Td numeric>{formatDecimal(Math.abs(p.reference - p.current))}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          }
        >
          <LineChart data={cdf}>
            <CartesianGrid vertical={false} stroke="var(--color-chart-grid)" />
            <XAxis
              dataKey="score"
              type="number"
              domain={[0, 1]}
              ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
              tick={axisTick}
              tickLine={false}
              tickFormatter={(v) => formatRatio(Number(v))}
            />
            <YAxis tick={axisTick} tickLine={false} axisLine={false} domain={[0, 1]} tickFormatter={(v) => formatRatio(Number(v))} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => formatDecimal(Number(v))} labelFormatter={(v) => `Оценка не выше ${formatRatio(Number(v))}`} />
            <Legend verticalAlign="top" align="right" content={(props) => <ChartLegend payload={props.payload} />} />
            <ReferenceLine
              x={gap.score}
              stroke="var(--color-chart-threshold)"
              strokeDasharray="6 4"
              label={{ value: `D = ${formatDecimal(s.statistic)}`, position: 'insideTopRight', fill: 'var(--color-chart-threshold)', fontSize: 12 }}
            />
            <Line type="monotone" dataKey="reference" name="Эталон" stroke="var(--color-chart-reference)" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="current" name="Текущий период" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ChartCard>
      </div>
    </div>
  );
}
