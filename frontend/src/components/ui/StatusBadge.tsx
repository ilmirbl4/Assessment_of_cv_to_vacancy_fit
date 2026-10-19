import { AlertTriangle, Check, CheckCircle, EyeOff, Minus, X, XCircle } from 'lucide-react';
import { Badge, type BadgeTone } from './Badge';
import { Spinner } from './Spinner';

export type StatusKind =
  | 'covered'
  | 'partially_covered'
  | 'not_covered'
  | 'inactive'
  | 'running'
  | 'success'
  | 'partial'
  | 'failed'
  | 'ok'
  | 'drift';

const config: Record<StatusKind, { label: string; tone: BadgeTone; icon: typeof Check | null }> = {
  covered: { label: 'Покрыто', tone: 'success', icon: Check },
  partially_covered: { label: 'Частично покрыто', tone: 'warning', icon: Minus },
  not_covered: { label: 'Не покрыто', tone: 'danger', icon: X },
  inactive: { label: 'Снята с публикации', tone: 'inactive', icon: EyeOff },
  running: { label: 'Выполняется', tone: 'primary', icon: null },
  success: { label: 'Успешно', tone: 'success', icon: CheckCircle },
  partial: { label: 'Частично', tone: 'warning', icon: AlertTriangle },
  failed: { label: 'Ошибка', tone: 'danger', icon: XCircle },
  ok: { label: 'Норма', tone: 'success', icon: CheckCircle },
  drift: { label: 'Предупреждение: дрейф', tone: 'warning', icon: AlertTriangle },
};

/**
 * Бейдж статуса с иконкой и текстом (цвет не единственный признак).
 * @param kind вид статуса
 */
export function StatusBadge({ kind }: { kind: StatusKind }) {
  const { label, tone, icon: Icon } = config[kind];
  return (
    <Badge tone={tone}>
      {Icon ? <Icon aria-hidden="true" size={14} strokeWidth={2} /> : <Spinner size={16} />}
      {label}
    </Badge>
  );
}
