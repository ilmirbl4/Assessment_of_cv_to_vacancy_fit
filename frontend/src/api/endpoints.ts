import { request } from './client';
import type {
  CollectionDashboard,
  Consent,
  Dictionaries,
  DriftDashboard,
  FavoriteItem,
  MatchFilters,
  MatchPage,
  Resume,
  SpeedDashboard,
  User,
  VacancyDetail,
} from './types';

/** Типизированные вызовы эндпоинтов REST API (раздел 4.3). */

export const api = {
  me: () => request<User>('GET', '/auth/me'),
  register: (body: { email: string; password: string; consent_accepted: true; consent_version: string }) =>
    request<void>('POST', '/auth/register', { body }),
  login: (body: { email: string; password: string }) => request<User>('POST', '/auth/login', { body }),
  logout: () => request<void>('POST', '/auth/logout'),
  confirmEmail: (token: string) => request<void>('POST', '/auth/confirm-email', { body: { token } }),
  resendConfirmation: (email: string) => request<void>('POST', '/auth/resend-confirmation', { body: { email } }),
  requestPasswordReset: (email: string) =>
    request<void>('POST', '/auth/password-reset/request', { body: { email } }),
  confirmPasswordReset: (body: { token: string; new_password: string }) =>
    request<void>('POST', '/auth/password-reset/confirm', { body }),
  consent: () => request<Consent>('GET', '/consent/current'),
  deleteAccount: () => request<void>('DELETE', '/account'),

  resume: () => request<Resume>('GET', '/resume'),
  uploadResume: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<Resume>('PUT', '/resume', { form });
  },
  deleteResume: () => request<void>('DELETE', '/resume'),

  dictionaries: () => request<Dictionaries>('GET', '/dictionaries'),
  startMatching: (filters: MatchFilters) => request<MatchPage>('POST', '/matching/runs', { body: { filters } }),
  currentMatching: (page: number) => request<MatchPage>('GET', '/matching/runs/current', { query: { page } }),

  vacancy: (id: string) => request<VacancyDetail>('GET', `/vacancies/${encodeURIComponent(id)}`),
  favorites: () => request<FavoriteItem[]>('GET', '/favorites'),
  addFavorite: (vacancyId: string) => request<void>('POST', '/favorites', { body: { vacancy_id: vacancyId } }),
  removeFavorite: (vacancyId: string) =>
    request<void>('DELETE', `/favorites/${encodeURIComponent(vacancyId)}`),

  adminCollection: (days = 30) => request<CollectionDashboard>('GET', '/admin/collection', { query: { days } }),
  startCollection: () => request<{ run_id: string }>('POST', '/admin/collection/runs'),
  adminSpeed: (days = 30) => request<SpeedDashboard>('GET', '/admin/matching-speed', { query: { days } }),
  adminDrift: (from?: string, to?: string) =>
    request<DriftDashboard>('GET', '/admin/drift', { query: { from, to } }),
};
