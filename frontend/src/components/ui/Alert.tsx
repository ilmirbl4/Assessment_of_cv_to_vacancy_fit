import type { ReactNode } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { cn } from '../../lib/cn';

export type AlertVariant = 'info' | 'success' | 'warning' | 'danger';

const styles: Record<AlertVariant, { box: string; icon: typeof Info }> = {
  info: { box: 'border-info bg-info-soft text-text [&_svg:first-child]:text-info', icon: Info },
  success: { box: 'border-success bg-success-soft text-text [&_svg:first-child]:text-success', icon: CheckCircle },
  warning: { box: 'border-warning bg-warning-soft text-text [&_svg:first-child]:text-warning', icon: AlertTriangle },
  danger: { box: 'border-danger bg-danger-soft text-text [&_svg:first-child]:text-danger', icon: AlertCircle },
};

interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children?: ReactNode;
  /** Кнопки или ссылки под текстом. */
  actions?: ReactNode;
  /** По умолчанию alert для ошибок и status для остальных. */
  role?: 'alert' | 'status';
  className?: string;
}

/**
 * Сообщение с цветной полосой слева и иконкой.
 * @param props вариант, заголовок, текст и действия
 */
export function Alert({ variant = 'info', title, children, actions, role, className }: AlertProps) {
  const { box, icon: Icon } = styles[variant];
  return (
    <div
      role={role ?? (variant === 'danger' ? 'alert' : 'status')}
      className={cn('flex gap-3 rounded-md border-l-4 p-4', box, className)}
    >
      <Icon aria-hidden="true" size={20} strokeWidth={2} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1 text-base">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className={cn(title && 'mt-1')}>{children}</div> : null}
        {actions ? <div className="mt-3 flex flex-wrap items-center gap-3">{actions}</div> : null}
      </div>
    </div>
  );
}
