import { type ReactNode, useId } from 'react';
import { AlertCircle } from 'lucide-react';
import { cn } from '../../lib/cn';

export interface FieldControlProps {
  id: string;
  'aria-describedby'?: string;
  'aria-invalid'?: true;
}

interface FieldProps {
  label: string;
  error?: string;
  hint?: string;
  className?: string;
  /** Получает id и aria-атрибуты для контрола. */
  children: (props: FieldControlProps) => ReactNode;
}

/**
 * Обёртка поля формы: подпись, контрол, подсказка или ошибка (ошибка заменяет подсказку).
 * @param props подпись, текст ошибки/подсказки и render-функция контрола
 */
export function Field({ label, error, hint, className, children }: FieldProps) {
  const id = useId();
  const messageId = `${id}-message`;
  const hasMessage = Boolean(error || hint);
  return (
    <div className={cn('flex flex-col', className)}>
      <label htmlFor={id} className="mb-1.5 text-sm font-medium text-text">
        {label}
      </label>
      {children({
        id,
        'aria-describedby': hasMessage ? messageId : undefined,
        'aria-invalid': error ? true : undefined,
      })}
      {error ? (
        <p id={messageId} className="mt-1.5 flex items-start gap-1.5 text-sm text-danger">
          <AlertCircle aria-hidden="true" size={16} strokeWidth={2} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </p>
      ) : hint ? (
        <p id={messageId} className="mt-1.5 text-sm text-text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
