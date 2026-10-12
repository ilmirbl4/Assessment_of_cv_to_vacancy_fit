import { CartesianGrid, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts';
import type { DriftDashboard } from '../../api/types';
import { Alert } from '../../components/ui/Alert';
import { Card } from '../../components/ui/Card';
import { Table, Td, Th } from '../../components/ui/Table';
import { formatDate, formatDecimal, formatRatio } from '../../lib/format';
import { rocExceeded } from './api';
import { ChartCard, axisTick, shortDate, tooltipStyle } from './ChartCard';

/**
 * Секция «Состязательная валидация»: предупреждение, график ROC-AUC по периодам и 5 важнейших признаков.
 * @param data данные дашборда дрейфа
 */
export function AdversarialSection({ data }: { data: DriftDashboard }) {
  const { periods, roc_auc_threshold, top_features } = data.adversarial;
  const last = periods.at(-1);
  const features = [...top_features].sort((a, b) => b.importance - a.importance);
  const maxImportance = Math.max(...features.map((f) => f.importance), 0.0001);
  const points = periods.map((p) => ({ label: `${shortDate(p.from)}–${shortDate(p.to)}`, roc_auc: p.roc_auc }));

  return (
    <Card title="Состязательная валидация">
      {last && rocExceeded(data) ? (
        <Alert variant="warning" className="mb-4">
          ROC-AUC = {formatDecimal(last.roc_auc)} превышает порог {formatRatio(roc_auc_threshold)}: распределение вакансий
          текущего периода заметно отличается от эталонного
        </Alert>
      ) : null}
      <div className="grid grid-cols-2 gap-6">
        <div className="flex flex-col gap-4">
          <ChartCard title="ROC-AUC по периодам" unit="Чем выше значение, тем сильнее отличаются периоды" height={200}>
            <LineChart data={points}>
              <CartesianGrid vertical={false} stroke="var(--color-chart-grid)" />
              <XAxis dataKey="label" tick={axisTick} tickLine={false} tickMargin={8} />
              <YAxis tick={axisTick} tickLine={false} axisLine={false} domain={[0.4, 0.8]} tickFormatter={(v) => formatRatio(Number(v))} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v) => formatDecimal(Number(v))} />
              <ReferenceLine
                y={roc_auc_threshold}
                stroke="var(--color-chart-threshold)"
                strokeDasharray="6 4"
                label={{ value: `Порог ${formatRatio(roc_auc_threshold)}`, position: 'insideTopLeft', fill: 'var(--color-chart-threshold)', fontSize: 12 }}
              />
              <Line type="monotone" dataKey="roc_auc" name="ROC-AUC" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ChartCard>
          <Table caption="ROC-AUC по периодам">
            <thead>
              <tr>
                <Th>Период</Th>
                <Th numeric>ROC-AUC</Th>
              </tr>
            </thead>
            <tbody>
              {periods.map((p) => (
                <tr key={p.from}>
                  <Td>
                    {formatDate(p.from)} – {formatDate(p.to)}
                  </Td>
                  <Td numeric>{formatDecimal(p.roc_auc)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
        <div>
          <h3 className="text-lg font-semibold">5 наиболее важных признаков</h3>
          <ol className="mt-4 flex flex-col gap-4">
            {features.map((f) => (
              <li key={f.name}>
                <div className="flex items-baseline justify-between gap-4 text-sm">
                  <span data-user-content>{f.name}</span>
                  <span className="tabular">{formatDecimal(f.importance)}</span>
                </div>
                <div className="mt-1 h-2 rounded-full bg-surface-muted" aria-hidden="true">
                  <div className="h-full rounded-full bg-chart-1" style={{ width: `${(f.importance / maxImportance) * 100}%` }} />
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </Card>
  );
}
