/**
 * Чип навыка. Текст приходит от сервера, поэтому помечен data-user-content.
 * @param children название навыка
 */
export function Chip({ children }: { children: string }) {
  return (
    <span data-user-content className="rounded-sm bg-surface-muted px-2.5 py-1 text-sm">
      {children}
    </span>
  );
}
