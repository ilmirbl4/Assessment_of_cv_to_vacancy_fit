import type { ComponentProps } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '../../lib/cn';
import { controlClasses } from './Input';

/**
 * Выпадающий список на базе нативного select (доступен с клавиатуры и скринридерам).
 * @param props стандартные атрибуты select; пункты передаются как option
 */
export function Select({ className, children, ...rest }: ComponentProps<'select'>) {
  return (
    <div className="relative">
      <select className={cn(controlClasses, 'appearance-none pr-9', className)} {...rest}>
        {children}
      </select>
      <ChevronDown
        aria-hidden="true"
        size={16}
        strokeWidth={2}
        className="pointer-events-none absolute right-3 top-3 text-text-muted"
      />
    </div>
  );
}
