import type { ComponentProps } from 'react';
import { Link } from 'react-router';
import { type ButtonSize, type ButtonVariant, buttonClasses } from '../../lib/buttonStyles';
import { cn } from '../../lib/cn';

interface ButtonLinkProps extends ComponentProps<typeof Link> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

/**
 * Ссылка маршрута, оформленная как кнопка.
 * @param props адрес `to`, вариант и размер кнопки
 */
export function ButtonLink({ variant = 'primary', size = 'md', className, ...rest }: ButtonLinkProps) {
  return <Link className={cn(buttonClasses(variant, size), className)} {...rest} />;
}
