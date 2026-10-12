import { Navigate, Outlet, useLocation, useSearchParams } from 'react-router';
import { homePath, isIntentionalExit, useMe } from '../features/auth/api';
import type { Role } from '../api/types';
import { QueryErrorView } from '../components/layout/QueryErrorView';
import { ForbiddenView } from '../pages/ForbiddenPage';
import { Spinner } from '../components/ui/Spinner';
import { safeNext } from '../lib/validation';

/** Полноэкранный спиннер проверки сессии. */
function SessionSpinner() {
  return (
    <div role="status" className="flex min-h-screen items-center justify-center text-primary">
      <Spinner size={24} />
      <span className="sr-only">Загрузка…</span>
    </div>
  );
}

/**
 * Пускает только гостей: вошедший пользователь уходит на безопасный `next` или домашнюю страницу роли.
 */
export function GuestOnly() {
  const me = useMe();
  const [params] = useSearchParams();
  if (me.isPending) return <SessionSpinner />;
  if (me.isError) return <QueryErrorView error={me.error} onRetry={() => void me.refetch()} />;
  if (me.data) return <Navigate to={safeNext(params.get('next')) ?? homePath(me.data.role)} replace />;
  return <Outlet />;
}

/**
 * Защита маршрутов по роли (ТЗ п. 4.2.2): гость → вход, чужая роль → редирект или страница 403.
 * @param allow требуемая роль
 */
export function RequireRole({ allow }: { allow: Role }) {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return <SessionSpinner />;
  if (me.isError) return <QueryErrorView error={me.error} onRetry={() => void me.refetch()} />;
  if (!me.data) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={isIntentionalExit() ? '/login' : `/login?next=${next}`} replace />;
  }
  if (me.data.role !== allow) {
    return allow === 'admin' ? <ForbiddenView withHeader /> : <Navigate to={homePath(me.data.role)} replace />;
  }
  return <Outlet />;
}
