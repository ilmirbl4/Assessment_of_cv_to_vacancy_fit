import { Navigate, createBrowserRouter } from 'react-router';
import { FavoritesPage } from '../features/favorites/FavoritesPage';
import { MatchingPage } from '../features/matching/MatchingPage';
import { ProfilePage } from '../features/profile/ProfilePage';
import { VacancyPage } from '../features/vacancy/VacancyPage';
import { AppLayout } from '../components/layout/AppLayout';
import { AuthLayout } from '../components/layout/AuthLayout';
import { PublicLayout } from '../components/layout/PublicLayout';
import { ConfirmEmailPage } from '../features/auth/ConfirmEmailPage';
import { ForgotPasswordPage } from '../features/auth/ForgotPasswordPage';
import { LoginPage } from '../features/auth/LoginPage';
import { RegisterDonePage } from '../features/auth/RegisterDonePage';
import { RegisterPage } from '../features/auth/RegisterPage';
import { ResetPasswordPage } from '../features/auth/ResetPasswordPage';
import { ConsentPage } from '../pages/ConsentPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { GuestOnly, RequireRole } from './guards';
import { RootLayout } from './providers';

/** Таблица маршрутов приложения (раздел 7.1). */
export const routes = [
  {
    element: <RootLayout />,
    HydrateFallback: () => null,
    children: [
      {
        element: <GuestOnly />,
        children: [
          {
            element: <AuthLayout />,
            children: [
              { path: '/login', element: <LoginPage /> },
              { path: '/register', element: <RegisterPage /> },
              { path: '/register/done', element: <RegisterDonePage /> },
              { path: '/forgot-password', element: <ForgotPasswordPage /> },
              { path: '/reset-password', element: <ResetPasswordPage /> },
            ],
          },
        ],
      },
      {
        element: <RequireRole allow="seeker" />,
        children: [
          {
            element: <AppLayout />,
            children: [
              { path: '/', element: <MatchingPage /> },
              { path: '/vacancies/:id', element: <VacancyPage /> },
              { path: '/favorites', element: <FavoritesPage /> },
              { path: '/profile', element: <ProfilePage /> },
            ],
          },
        ],
      },
      {
        element: <RequireRole allow="admin" />,
        children: [
          {
            element: <AppLayout />,
            children: [
              {
                path: '/admin',
                // Админка (с графиками recharts) грузится отдельным чанком.
                lazy: async () => ({ Component: (await import('../features/admin/AdminLayout')).AdminLayout }),
                children: [
                  { index: true, element: <Navigate to="/admin/collection" replace /> },
                  { path: 'collection', lazy: async () => ({ Component: (await import('../features/admin/CollectionPage')).CollectionPage }) },
                  { path: 'speed', lazy: async () => ({ Component: (await import('../features/admin/SpeedPage')).SpeedPage }) },
                  {
                    path: 'drift',
                    lazy: async () => ({ Component: (await import('../features/admin/DriftPage')).DriftPage }),
                    children: [
                      { index: true, lazy: async () => ({ Component: (await import('../features/admin/DriftPage')).DriftIndex }) },
                      { path: 'data', lazy: async () => ({ Component: (await import('../features/admin/DriftPage')).DriftInputsView }) },
                      { path: 'model', lazy: async () => ({ Component: (await import('../features/admin/DriftPage')).DriftModelView }) },
                      { path: 'feedback', lazy: async () => ({ Component: (await import('../features/admin/DriftPage')).DriftFeedbackView }) },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
      { element: <AuthLayout />, children: [{ path: '/confirm-email', element: <ConfirmEmailPage /> }] },
      {
        element: <PublicLayout />,
        children: [
          { path: '/consent', element: <ConsentPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
      ...(import.meta.env.DEV
        ? [
            {
              path: '/__ui',
              lazy: async () => ({ Component: (await import('../pages/UiKitPage')).UiKitPage }),
            },
          ]
        : []),
    ],
  },
];

/** Создаёт браузерный роутер. */
export function createAppRouter() {
  return createBrowserRouter(routes);
}
