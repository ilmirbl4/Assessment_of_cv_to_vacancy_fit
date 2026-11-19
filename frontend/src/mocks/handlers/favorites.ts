import { HttpResponse } from 'msw';
import type { FavoriteItem } from '../../api/types';
import { saveDb } from '../db';
import { VACANCIES } from '../seed';
import { authorize, err, noContent, route } from './common';

export const favoritesHandlers = [
  route('get', '/favorites', () => {
    const auth = authorize('seeker');
    if ('response' in auth) return auth.response;
    const list = [...(auth.db.favorites[auth.user.id] ?? [])].sort((a, b) => b.added_at.localeCompare(a.added_at));
    const items: FavoriteItem[] = list.flatMap((fav) => {
      const v = VACANCIES.find((x) => x.id === fav.vacancy_id);
      if (!v) return [];
      return [
        {
          vacancy: {
            id: v.id,
            title: v.title,
            salary_from: v.salary_from,
            salary_to: v.salary_to,
            employer_name: v.employer_name,
            published_at: v.published_at,
          },
          is_active: v.is_active,
          added_at: fav.added_at,
        },
      ];
    });
    return HttpResponse.json(items);
  }),

  route('post', '/favorites', async ({ request }) => {
    const auth = authorize('seeker');
    if ('response' in auth) return auth.response;
    const body = (await request.json()) as { vacancy_id?: string };
    if (!VACANCIES.some((v) => v.id === body.vacancy_id)) {
      return err(404, 'VACANCY_NOT_FOUND', 'Вакансия не найдена');
    }
    const list = (auth.db.favorites[auth.user.id] ??= []);
    if (list.some((f) => f.vacancy_id === body.vacancy_id)) {
      return err(409, 'ALREADY_IN_FAVORITES', 'Вакансия уже в избранном');
    }
    list.push({ vacancy_id: body.vacancy_id as string, added_at: new Date().toISOString() });
    saveDb(auth.db);
    return HttpResponse.json({}, { status: 201 });
  }),

  route('delete', '/favorites/:id', ({ params }) => {
    const auth = authorize('seeker');
    if ('response' in auth) return auth.response;
    auth.db.favorites[auth.user.id] = (auth.db.favorites[auth.user.id] ?? []).filter(
      (f) => f.vacancy_id !== params.id,
    );
    saveDb(auth.db);
    return noContent();
  }),
];
