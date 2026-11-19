import { HttpResponse } from 'msw';
import type { MatchFilters, MatchPage, VacancyCard, VacancyDetail } from '../../api/types';
import { MSG, minSalarySchema } from '../../lib/validation';
import { type DbState, type StoredRun, saveDb } from '../db';
import { DICTIONARIES, REGIONS, type SeedVacancy, VACANCIES, buildRequirements, matchPercentOf } from '../seed';
import { authorize, err, route } from './common';
import { currentResume } from './resume';

const PAGE_SIZE = 10;
const MAX_RESULTS = 100;

/** Содержимое готового резюме пользователя или null, если готового резюме нет. */
function readySkills(db: DbState, userId: string): string[] | null {
  const resume = currentResume(db, userId);
  return resume && resume.status === 'ready' ? db.resumes[userId].skills : null;
}

/** Процент соответствия резюме требованиям вакансии. */
function matchPercent(vacancy: SeedVacancy, skills: string[]): number {
  return matchPercentOf(buildRequirements(vacancy, skills));
}

function toCard(vacancy: SeedVacancy, percent: number): VacancyCard {
  return {
    id: vacancy.id,
    title: vacancy.title,
    salary_from: vacancy.salary_from,
    salary_to: vacancy.salary_to,
    employer_name: vacancy.employer_name,
    published_at: vacancy.published_at,
    match_percent: percent,
  };
}

/** Применяет фильтры подбора к активным вакансиям. */
function applyFilters(filters: MatchFilters): SeedVacancy[] {
  return VACANCIES.filter((v) => {
    if (!v.is_active) return false;
    if (filters.region_code && v.region_code !== filters.region_code) return false;
    if (filters.employment_type && v.employment_type !== filters.employment_type) return false;
    if (filters.schedule && v.schedule !== filters.schedule) return false;
    if (filters.experience && v.experience !== filters.experience) return false;
    const top = Math.max(v.salary_from ?? 0, v.salary_to ?? 0);
    const hasSalary = v.salary_from !== null || v.salary_to !== null;
    if (filters.only_with_salary && !hasSalary) return false;
    if (filters.min_salary !== null && (!hasSalary || top < filters.min_salary)) return false;
    return true;
  });
}

function buildPage(db: DbState, userId: string, run: StoredRun, page: number): MatchPage {
  const skills = readySkills(db, userId) ?? [];
  const total = run.ids.length;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const safePage = Math.min(Math.max(page, 1), Math.max(totalPages, 1));
  const items = run.ids
    .slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)
    .map((id) => VACANCIES.find((v) => v.id === id) as SeedVacancy)
    .map((v) => toCard(v, matchPercent(v, skills)));
  return {
    run_id: run.run_id,
    created_at: run.created_at,
    filters: run.filters,
    total,
    page: safePage,
    page_size: PAGE_SIZE,
    total_pages: totalPages,
    items,
  };
}

export const matchingHandlers = [
  route('get', '/dictionaries', () => HttpResponse.json(DICTIONARIES)),

  route('post', '/matching/runs', async ({ request }) => {
    const auth = authorize('seeker');
    if ('response' in auth) return auth.response;
    const { db, user } = auth;
    const body = (await request.json()) as { filters?: MatchFilters };
    const filters = body.filters;
    if (!filters) return err(422, 'VALIDATION_ERROR', 'Проверьте введённые данные');
    const salaryText = filters.min_salary === null ? '' : String(filters.min_salary);
    if (!minSalarySchema.safeParse(salaryText).success) {
      return err(422, 'VALIDATION_ERROR', 'Проверьте введённые данные', { min_salary: MSG.salary });
    }
    if (!db.resumes[user.id]) return err(409, 'RESUME_NOT_FOUND', 'Для подбора вакансий загрузите резюме.');
    const skills = readySkills(db, user.id);
    if (!skills) return err(409, 'RESUME_NOT_READY', 'Резюме ещё обрабатывается');

    const ids = applyFilters(filters)
      .map((v) => ({ v, percent: matchPercent(v, skills) }))
      .sort(
        (a, b) =>
          b.percent - a.percent ||
          b.v.published_at.localeCompare(a.v.published_at) ||
          Number(a.v.id) - Number(b.v.id),
      )
      .slice(0, MAX_RESULTS)
      .map(({ v }) => v.id);

    db.counter += 1;
    const run: StoredRun = { run_id: `run-${db.counter}`, created_at: new Date().toISOString(), filters, ids };
    db.runs[user.id] = run;
    saveDb(db);
    return HttpResponse.json(buildPage(db, user.id, run, 1), { status: 201 });
  }),

  route('get', '/matching/runs/current', ({ request }) => {
    const auth = authorize('seeker');
    if ('response' in auth) return auth.response;
    const run = auth.db.runs[auth.user.id];
    if (!run) return err(404, 'NO_MATCH_RUN', 'Подбор ещё не запускался');
    const page = Number(new URL(request.url).searchParams.get('page') ?? '1');
    return HttpResponse.json(buildPage(auth.db, auth.user.id, run, Number.isFinite(page) ? page : 1));
  }),

  route('get', '/vacancies/:id', ({ params }) => {
    const auth = authorize('seeker');
    if ('response' in auth) return auth.response;
    const vacancy = VACANCIES.find((v) => v.id === params.id);
    if (!vacancy) return err(404, 'VACANCY_NOT_FOUND', 'Вакансия не найдена');
    const skills = readySkills(auth.db, auth.user.id);
    const detail: VacancyDetail = {
      ...toCard(vacancy, 0),
      match_percent: skills ? matchPercent(vacancy, skills) : null,
      region_name: REGIONS.find((r) => r.code === vacancy.region_code)?.name ?? '',
      source_url: `https://trudvsem.ru/vacancy/card/${vacancy.id}`,
      is_active: vacancy.is_active,
      is_favorite: (auth.db.favorites[auth.user.id] ?? []).some((f) => f.vacancy_id === vacancy.id),
      source_fields: vacancy.source_fields,
      requirements: skills ? buildRequirements(vacancy, skills) : [],
    };
    return HttpResponse.json(detail);
  }),
];
