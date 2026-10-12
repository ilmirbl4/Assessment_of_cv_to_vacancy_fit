import { type ComponentProps, type ReactNode, useId } from 'react';
import { AlertCircle, Check } from 'lucide-react';

interface CheckboxProps extends Omit<ComponentProps<'input'>, 'type' | 'children'> {
  label: ReactNode;
  /** Дополнительный элемент справа от подписи (например, ссылка). */
  suffix?: ReactNode;
  error?: string;
}

/**
 * Флажок 18px: клик по подписи тоже переключает; ошибка выводится под флажком.
 * @param props подпись, ошибка и стандартные атрибуты input
 */
export function Checkbox({ label, suffix, error, id, ...rest }: CheckboxProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const errorId = `${inputId}-error`;
  return (
    <div>
      <div className="flex items-start gap-3">
        <span className="relative mt-0.5 inline-flex shrink-0">
          <input
            id={inputId}
            type="checkbox"
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? errorId : undefined}
            className="peer size-4.5 cursor-pointer appearance-none rounded-sm border border-border-strong bg-surface checked:border-primary checked:bg-primary aria-invalid:border-danger"
            {...rest}
          />
          <Check
            aria-hidden="true"
            strokeWidth={3}
            className="pointer-events-none absolute left-0.5 top-0.5 hidden size-3.5 text-on-primary peer-checked:block"
          />
        </span>
        <label htmlFor={inputId} className="cursor-pointer text-base text-text">
          {label}
        </label>
        {suffix}
      </div>
      {error ? (
        <p id={errorId} className="mt-1.5 flex items-start gap-1.5 text-sm text-danger">
          <AlertCircle aria-hidden="true" size={16} strokeWidth={2} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  );
}
