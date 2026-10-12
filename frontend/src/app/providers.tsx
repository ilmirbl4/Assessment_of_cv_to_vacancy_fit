import { useEffect, useRef } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { Outlet, useLocation, useNavigate } from 'react-router';
import { setUnauthorizedHandler } from '../api/client';
import { ToastProvider, useToast } from '../components/ui/Toast';
import { ME_KEY, isIntentionalExit } from '../features/auth/api';
import { queryClient } from './queryClient';

/** Подключает общую реакцию на 401: очистка кэша, Toast и переход на вход с `next`. */
function SessionBridge() {
  const navigate = useNavigate();
  const toast = useToast();
  const location = useLocation();
  const currentPath = useRef(location.pathname + location.search);
  useEffect(() => {
    currentPath.current = location.pathname + location.search;
  }, [location]);
  useEffect(() => {
    let handling = false;
    setUnauthorizedHandler(() => {
      // После выхода по кнопке или для известного гостя 401 ожидаем: переход на вход делают guards.
      if (isIntentionalExit() || queryClient.getQueryData(ME_KEY) === null) return;
      if (handling) return;
      handling = true;
      setTimeout(() => (handling = false), 1000);
      const next = encodeURIComponent(currentPath.current);
      queryClient.clear();
      toast('Сеанс завершён. Войдите снова.', 'info');
      navigate(`/login?next=${next}`, { replace: true });
    });
    return () => setUnauthorizedHandler(null);
  }, [navigate, toast]);
  return null;
}

/** Корневой маршрут: провайдеры React Query и уведомлений. */
export function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <SessionBridge />
        <Outlet />
      </ToastProvider>
    </QueryClientProvider>
  );
}
