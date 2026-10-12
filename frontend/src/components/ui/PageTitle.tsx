import { useEffect } from 'react';

/**
 * Заголовок страницы (h1) и `<title>` вкладки вида «Название — Подбор вакансий».
 * @param title название страницы
 * @param documentTitle отдельный текст для вкладки (если отличается от h1)
 */
export function PageTitle({
  title,
  documentTitle,
  className,
  userContent = false,
}: {
  title: string;
  documentTitle?: string;
  className?: string;
  /** Заголовок пришёл от сервера (название вакансии) и помечается data-user-content. */
  userContent?: boolean;
}) {
  useDocumentTitle(documentTitle ?? title);
  return (
    <h1 className={className ?? 'text-2xl font-semibold'} data-user-content={userContent || undefined}>
      {title}
    </h1>
  );
}

/**
 * Устанавливает `<title>` вкладки.
 * @param title название страницы
 */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} — Подбор вакансий`;
  }, [title]);
}
