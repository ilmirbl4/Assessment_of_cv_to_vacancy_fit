import { Outlet } from 'react-router';
import { AppHeader } from './AppHeader';
import { PageContainer } from './PageContainer';

/** Макет страниц после входа: шапка и контейнер. Страницы сами не рисуют шапку. */
export function AppLayout({ narrow = false }: { narrow?: boolean }) {
  return (
    <>
      <AppHeader />
      <PageContainer narrow={narrow}>
        <Outlet />
      </PageContainer>
    </>
  );
}
