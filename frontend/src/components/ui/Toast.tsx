import { type ReactNode, createContext, useCallback, useContext, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle, Info } from 'lucide-react';

type ToastTone = 'success' | 'info' | 'danger';
interface ToastItem {
  id: number;
  tone: ToastTone;
  message: string;
}

const icons = { success: CheckCircle, info: Info, danger: AlertCircle };
const iconColors: Record<ToastTone, string> = { success: 'text-success', info: 'text-info', danger: 'text-danger' };
const TOAST_MS = 4000;

const ToastContext = createContext<((message: string, tone?: ToastTone) => void) | null>(null);

/**
 * Провайдер уведомлений: показывает Toast в правом нижнем углу на 4 секунды.
 * @param children приложение
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const [counter, setCounter] = useState(0);

  const show = useCallback(
    (message: string, tone: ToastTone = 'success') => {
      const id = counter + 1;
      setCounter(id);
      setItems((list) => [...list, { id, tone, message }]);
      setTimeout(() => setItems((list) => list.filter((t) => t.id !== id)), TOAST_MS);
    },
    [counter],
  );
  const value = useMemo(() => show, [show]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex flex-col gap-3">
        {items.map((item) => {
          const Icon = icons[item.tone];
          return (
            <div
              key={item.id}
              role="status"
              className="pointer-events-auto flex w-90 items-start gap-3 rounded-lg border border-border bg-surface p-4 shadow-raised"
            >
              <Icon aria-hidden="true" size={20} strokeWidth={2} className={`mt-0.5 shrink-0 ${iconColors[item.tone]}`} />
              <p className="text-base">{item.message}</p>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

/** Возвращает функцию показа Toast: `toast('Текст', 'success')`. */
export function useToast(): (message: string, tone?: ToastTone) => void {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast должен вызываться внутри ToastProvider');
  return ctx;
}
