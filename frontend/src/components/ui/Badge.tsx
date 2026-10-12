import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

export type BadgeTone = 'success' | 'warning' | 'danger' | 'neutral' | 'primary' | 'inactive';

const tones: Record<BadgeTone, string> = {
  success: 'bg-success-soft text-success',
  warning: 'bg-warning-soft text-warning',
  danger: 'bg-danger-soft text-danger',
  neutral: 'bg-surface-muted text-text-muted',
  primary: 'bg-primary-soft text-primary',
  inactive: 'bg-inactive-border text-inactive-text',
};

/**
 * Базовая пилюля-бейдж с цветовым тоном.
 * @param props тон и содержимое
 */
export function Badge({
  tone = 'neutral',
  className,
  children,
  ...rest
}: { tone?: BadgeTone; className?: string; children: ReactNode; 'aria-label'?: string }) {
  return (
    <span
      className={cn('inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1 text-sm font-medium', tones[tone], className)}
      {...rest}
    >
      {children}
    </span>
  );
}
