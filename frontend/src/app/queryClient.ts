import { QueryClient } from '@tanstack/react-query';

/**
 * Создаёт клиент React Query: без автоповторов (ошибки сразу видны) и без обновления при фокусе окна.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
}

/** Единственный клиент приложения. */
export const queryClient = createQueryClient();
