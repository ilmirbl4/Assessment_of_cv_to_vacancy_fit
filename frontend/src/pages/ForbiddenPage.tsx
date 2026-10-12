import { ShieldAlert } from 'lucide-react';
import { AppHeader } from '../components/layout/AppHeader';
import { PageContainer } from '../components/layout/PageContainer';
import { ButtonLink } from '../components/ui/ButtonLink';
import { EmptyState } from '../components/ui/EmptyState';
import { useDocumentTitle } from '../components/ui/PageTitle';
import { homePath, useMe } from '../features/auth/api';

/**
 * Содержимое страницы 403.
 * @param withHeader нарисовать шапку и контейнер (когда страница показана вместо маршрута)
 */
export function ForbiddenView({ withHeader = false }: { withHeader?: boolean }) {
  const me = useMe().data;
  useDocumentTitle('Доступ запрещён');
  const content = (
    <EmptyState
      icon={ShieldAlert}
      title="Доступ запрещён"
      headingLevel={1}
      description="Доступ запрещён. У вашей учётной записи нет прав на просмотр этой страницы."
      action={<ButtonLink to={me ? homePath(me.role) : '/login'}>На главную</ButtonLink>}
    />
  );
  if (!withHeader) return content;
  return (
    <>
      <AppHeader />
      <PageContainer>{content}</PageContainer>
    </>
  );
}

/** Маршрут страницы 403. */
export function ForbiddenPage() {
  return <ForbiddenView withHeader />;
}
