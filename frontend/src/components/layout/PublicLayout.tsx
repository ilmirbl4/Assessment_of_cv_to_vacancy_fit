import { Outlet } from 'react-router';
import { useMe } from '../../features/auth/api';
import { AppHeader } from './AppHeader';
import { PageContainer } from './PageContainer';

/** Макет общедоступных страниц (согласие, 404): шапка с учётом роли. */
export function PublicLayout() {
  const me = useMe();
  if (me.isPending) return null;
  return (
    <>
      <AppHeader />
      <PageContainer>
        <Outlet />
      </PageContainer>
    </>
  );
}
