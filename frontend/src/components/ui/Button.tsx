import type { ComponentProps } from 'react';
import type { LucideIcon } from 'lucide-react';
import { type ButtonSize, type ButtonVariant, buttonClasses } from '../../lib/buttonStyles';
import { cn } from '../../lib/cn';
import { Spinner } from './Spinner';

interface ButtonProps extends ComponentProps<'button'> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Показать спиннер и заблокировать кнопку на время запроса. */
  loading?: boolean;
  /** Иконка слева (16px). */
  icon?: LucideIcon;
  fullWidth?: boolean;
}

/**
 * Кнопка дизайн-системы: варианты primary/secondary/ghost/danger, состояния loading и disabled.
 * @param props варианты оформления и стандартные атрибуты button
 */
export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon: Icon,
  fullWidth = false,
  disabled,
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(buttonClasses(variant, size, fullWidth), className)}
      {...rest}
    >
      {loading ? <Spinner /> : Icon ? <Icon aria-hidden="true" size={16} strokeWidth={2} /> : null}
      {children}
    </button>
  );
}
