import { cn } from './cn';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'md' | 'sm';

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-on-primary hover:bg-primary-hover active:bg-primary-active',
  secondary: 'bg-surface text-text border border-border hover:bg-surface-muted',
  ghost: 'bg-transparent text-primary hover:bg-primary-soft',
  danger: 'bg-danger text-on-primary hover:bg-danger-hover',
};

const sizes: Record<ButtonSize, string> = {
  md: 'h-10 px-4 text-base',
  sm: 'h-8 px-3 text-sm',
};

/**
 * Возвращает классы кнопки (общие для Button и ссылок-кнопок).
 * @param variant вариант оформления
 * @param size размер
 * @param fullWidth растянуть на всю ширину
 */
export function buttonClasses(variant: ButtonVariant = 'primary', size: ButtonSize = 'md', fullWidth = false): string {
  return cn(
    'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium transition-colors',
    'disabled:cursor-not-allowed disabled:opacity-50 aria-disabled:cursor-not-allowed aria-disabled:opacity-50',
    variants[variant],
    sizes[size],
    fullWidth && 'w-full',
  );
}
