import type { ReactNode } from 'react';
import { Description, Dialog as HeadlessDialog, DialogBackdrop, DialogPanel, DialogTitle } from '@headlessui/react';

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  /** Пока true, окно не закрывается по Escape и клику по подложке. */
  busy?: boolean;
  description?: string;
  children?: ReactNode;
  /** Кнопки: «Отмена» первой (получает фокус), действие последним. */
  footer: ReactNode;
}

/**
 * Модальное окно 480px на базе Headless UI Dialog.
 * @param props заголовок, текст, кнопки и состояние
 */
export function Dialog({ open, onClose, title, busy = false, description, children, footer }: DialogProps) {
  return (
    <HeadlessDialog open={open} onClose={() => (busy ? undefined : onClose())} className="relative z-50">
      <DialogBackdrop className="fixed inset-0 bg-black/40" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <DialogPanel className="w-full max-w-120 rounded-xl bg-surface p-6 shadow-modal">
          <DialogTitle as="h2" className="text-xl font-semibold">
            {title}
          </DialogTitle>
          {description ? <Description className="mt-3 text-text">{description}</Description> : null}
          {children ? <div className="mt-4">{children}</div> : null}
          <div className="mt-6 flex justify-end gap-3">{footer}</div>
        </DialogPanel>
      </div>
    </HeadlessDialog>
  );
}
