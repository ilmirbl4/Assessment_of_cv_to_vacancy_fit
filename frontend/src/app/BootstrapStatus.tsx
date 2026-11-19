import { useQuery } from '@tanstack/react-query';

interface Status { phase: string; matching_ready: boolean; progress?: number; total?: number; error?: string | null }
const labels: Record<string, string> = { database: 'Подключение к базе', models: 'Проверка моделей', checking: 'Проверка данных', rebuild: 'Пересчёт', initial: 'Первоначальная загрузка', reference: 'Подготовка эталона', failed: 'Ошибка подготовки' };

/** Readiness is separate from liveness: the UI stays available during long imports. */
export function BootstrapStatus() {
  const query = useQuery({ queryKey: ['bootstrap'], queryFn: async (): Promise<Status> => {
    const response = await fetch('/api/v1/status');
    if (!response.ok) throw new Error('Состояние временно недоступно');
    return response.json() as Promise<Status>;
  }, refetchInterval: (q) => q.state.data?.matching_ready ? 15000 : 3000, retry: false });
  const status = query.data;
  if (!status || status.matching_ready) return null;
  return <aside role="status" className="border-b bg-warning-soft p-4 text-center">
    <strong>{labels[status.phase] ?? 'Подготовка системы'}</strong>
    <p>{status.error ?? 'Подбор станет доступен после завершения обработки.'}</p>
    {status.total ? <p>{status.progress ?? 0} / {status.total}</p> : null}
  </aside>;
}
