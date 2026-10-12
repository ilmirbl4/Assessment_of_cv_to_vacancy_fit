import type { ComponentProps } from 'react';
import { cn } from '../../lib/cn';

export const controlClasses =
  'h-10 w-full rounded-md border border-border bg-surface px-3 text-base text-text placeholder:text-text-muted ' +
  'hover:border-border-strong focus:border-primary disabled:cursor-not-allowed disabled:bg-surface-muted ' +
  'disabled:text-text-disabled aria-invalid:border-danger';

interface InputProps extends ComponentProps<'input'> {
  /** Суффикс справа, например «₽». */
  suffix?: string;
}

/**
 * Текстовое поле ввода высотой 40px.
 * @param props стандартные атрибуты input и необязательный суффикс
 */
export function Input({ suffix, className, ...rest }: InputProps) {
  if (!suffix) return <input className={cn(controlClasses, className)} {...rest} />;
  return (
    <div className="relative">
      <input className={cn(controlClasses, 'pr-9', className)} {...rest} />
      <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-text-muted">
        {suffix}
      </span>
    </div>
  );
}
