import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/cn';

/**
 * Индикатор загрузки. Декоративный: смысл передаёт окружающий текст.
 * @param size размер в пикселях (16, 20, 24)
 */
export function Spinner({ size = 16, className }: { size?: 16 | 20 | 24; className?: string }) {
  return <Loader2 aria-hidden="true" size={size} strokeWidth={2} className={cn('animate-spin', className)} />;
}
