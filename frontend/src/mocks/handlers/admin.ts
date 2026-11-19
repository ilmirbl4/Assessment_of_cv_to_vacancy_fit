import { HttpResponse } from 'msw';
import type {
  CollectionDashboard,
  CollectionRun,
  DistributionBin,
  DriftDashboard,
  FavoriteRateDay,
  ScoreDrift,
  SpeedDashboard,
  SpeedDay,
} from '../../api/types';
import { type DbState, mockConfig, saveDb } from '../db';
import { VACANCIES, createRng } from '../seed';
import { authorize, err, route } from './common';

const TODAY = '2026-10-12';

function isoDay(offsetFromToday: number): string {
  return new Date(Date.UTC(2026, 9, 12 + offsetFromToday)).toISOString().slice(0, 10);
}

/** 30 запусков сбора за 30 суток: один «failed» и один «partial». */
function seedRuns(): CollectionRun[] {
  const rng = createRng(777);
  return Array.from({ length: 30 }, (_, i) => {
    const day = isoDay(-i);
    const status = i === 9 ? 'failed' : i === 17 ? 'partial' : 'success';
    return {
      id: `c-${30 - i}`,
      started_at: `${day}T03:00:00+03:00`,
      finished_at: `${day}T03:${status === 'failed' ? '04' : '21'}:00+03:00`,
      status,
      new_count: status === 'failed' ? 0 : 40 + Math.floor(rng() * 160),
      updated_count: status === 'failed' ? 0 : 200 + Math.floor(rng() * 800),
      deactivated_count: status === 'failed' ? 0 : 10 + Math.floor(rng() * 90),
      error_count: status === 'failed' ? 14 : status === 'partial' ? 3 : 0,
    };
  });
}

/** Завершает фоновый запуск сбора, если время вышло, и возвращает дашборд. */
function collectionDashboard(db: DbState): CollectionDashboard {
  let changed = false;
  if (db.collection_running_until !== null && Date.now() >= db.collection_running_until) {
    db.collection_added.unshift({
      id: db.collection_running_id ?? 'c-new',
      started_at: new Date(db.collection_running_until - mockConfig.collectionMs).toISOString(),
      finished_at: new Date(db.collection_running_until).toISOString(),
      status: 'success',
      new_count: 12,
      updated_count: 87,
      deactivated_count: 4,
      error_count: 0,
    });
    db.collection_running_until = null;
    db.collection_running_id = null;
    changed = true;
  }
  if (changed) saveDb(db);
  return {
    active_vacancies_total: VACANCIES.filter((v) => v.is_active).length,
    is_running: db.collection_running_until !== null,
    runs: [...db.collection_added, ...seedRuns()],
  };
}

function speedDashboard(): SpeedDashboard {
  const rng = createRng(4242);
  const days: SpeedDay[] = Array.from({ length: 30 }, (_, i) => {
    const avg = Math.round(340 + 90 * Math.sin(i / 3) + rng() * 60);
    return { date: isoDay(i - 29), avg_ms: avg, p95_ms: Math.round(avg * 1.8 + rng() * 40), count: 30 + Math.floor(rng() * 50) };
  });
  return { days };
}

function bins(labels: string[], shares: number[]): DistributionBin[] {
  return labels.map((bin, i) => ({ bin, share: shares[i] }));
}

const SCORE_BINS = Array.from({ length: 10 }, (_, i) => `${formatTenth(i)}–${formatTenth(i + 1)}`);

/** «0,3» для i = 3. */
function formatTenth(i: number): string {
  return (i / 10).toLocaleString('ru-RU', { minimumFractionDigits: 1 });
}

/**
 * Асимптотическое p-значение двухвыборочного теста Колмогорова — Смирнова.
 * @param d статистика D
 * @param n размер первой выборки
 * @param m размер второй выборки
 */
function ksPValue(d: number, n: number, m: number): number {
  const en = Math.sqrt((n * m) / (n + m));
  const lambda = (en + 0.12 + 0.11 / en) * d;
  let sum = 0;
  for (let k = 1; k <= 100; k++) sum += 2 * (-1) ** (k - 1) * Math.exp(-2 * k * k * lambda * lambda);
  return Math.min(1, Math.max(0, sum));
}

/**
 * Оценки кросс-энкодера двугорбые (уверенные «не покрыто» у нуля и «покрыто» у единицы);
 * в текущем периоде больше уверенных «не покрыто» — распределение сместилось влево.
 */
function modelScores(): ScoreDrift {
  const reference = [0.22, 0.12, 0.07, 0.05, 0.04, 0.04, 0.05, 0.08, 0.13, 0.2];
  const current = [0.27, 0.14, 0.08, 0.06, 0.05, 0.04, 0.05, 0.07, 0.11, 0.13];
  let statistic = 0;
  let cumRef = 0;
  let cumCur = 0;
  for (let i = 0; i < reference.length; i++) {
    cumRef += reference[i];
    cumCur += current[i];
    statistic = Math.max(statistic, Math.abs(cumRef - cumCur));
  }
  const reference_size = 12480;
  const current_size = 1840;
  return {
    statistic: Math.round(statistic * 1000) / 1000,
    p_value: ksPValue(statistic, reference_size, current_size),
    alpha: 0.05,
    reference_size,
    current_size,
    reference: bins(SCORE_BINS, reference),
    current: bins(SCORE_BINS, current),
  };
}

/**
 * Доля подборов с добавлением в избранное по суткам периода (не более 92 последних суток).
 * С августа доля плавно снижается: 0,29 → 0,24 (в пределах допуска 5 п. п. от эталона 0,28).
 */
function favoriteDays(from: string, to: string): FavoriteRateDay[] {
  const start = Date.parse(`${from}T00:00:00Z`);
  const end = Date.parse(`${to}T00:00:00Z`);
  const DAY = 86_400_000;
  const first = Math.max(start, end - 91 * DAY);
  const trendStart = Date.parse('2026-08-01T00:00:00Z');
  const days: FavoriteRateDay[] = [];
  for (let t = first; t <= end; t += DAY) {
    const date = new Date(t).toISOString().slice(0, 10);
    const rng = createRng(Number(date.replaceAll('-', '')));
    const progress = Math.min(1, Math.max(0, (t - trendStart) / (72 * DAY)));
    const base = 0.29 - 0.05 * progress;
    const runs = 30 + Math.floor(rng() * 50);
    const withFavorite = Math.round(runs * Math.min(1, Math.max(0, base + (rng() - 0.5) * 0.08)));
    days.push({ date, runs, runs_with_favorite: withFavorite, share: withFavorite / runs });
  }
  return days;
}

function driftDashboard(from: string, to: string): DriftDashboard {
  const skillBins = ['0–4', '5–9', '10–14', '15–19', '20+'];
  const areaBins = ['ИТ', 'Финансы', 'Промышл.', 'Торговля', 'Образов.', 'Прочее'];
  const distanceBins = ['0–0,1', '0,1–0,2', '0,2–0,3', '0,3–0,4', '0,4–0,5', '0,5+'];
  const distanceLabel = 'Косинусное расстояние до центроида эталона';
  return {
    reference_period: { from: '2026-03-01', to: '2026-05-31' },
    current_period: { from, to },
    psi_threshold: 0.2,
    indicators: [
      {
        key: 'skills_per_vacancy',
        name: 'Число навыков на вакансию',
        entity: 'vacancies',
        bins_label: 'Навыков в требованиях',
        psi: 0.2,
        reference: bins(skillBins, [0.1, 0.3, 0.35, 0.2, 0.05]),
        current: bins(skillBins, [0.14, 0.32, 0.31, 0.17, 0.06]),
      },
      {
        key: 'professional_area',
        name: 'Распределение по профессиональным областям',
        entity: 'vacancies',
        bins_label: 'Профессиональная область',
        psi: 0.27,
        reference: bins(areaBins, [0.3, 0.2, 0.2, 0.15, 0.1, 0.05]),
        current: bins(areaBins, [0.18, 0.28, 0.12, 0.22, 0.08, 0.12]),
      },
      {
        key: 'vacancy_embeddings',
        name: 'Эмбеддинги вакансий',
        entity: 'vacancies',
        bins_label: distanceLabel,
        psi: 0.12,
        reference: bins(distanceBins, [0.12, 0.3, 0.28, 0.17, 0.09, 0.04]),
        current: bins(distanceBins, [0.1, 0.27, 0.29, 0.19, 0.1, 0.05]),
      },
      {
        key: 'resume_embeddings',
        name: 'Эмбеддинги резюме',
        entity: 'resumes',
        bins_label: distanceLabel,
        psi: 0.24,
        reference: bins(distanceBins, [0.15, 0.32, 0.27, 0.15, 0.07, 0.04]),
        current: bins(distanceBins, [0.08, 0.22, 0.27, 0.22, 0.13, 0.08]),
      },
    ],
    adversarial: {
      roc_auc_threshold: 0.6,
      periods: [
        { from: '2026-06-01', to: '2026-07-15', roc_auc: 0.52 },
        { from: '2026-07-16', to: '2026-08-31', roc_auc: 0.55 },
        { from: '2026-09-01', to: '2026-09-30', roc_auc: 0.58 },
        { from: '2026-10-01', to: TODAY, roc_auc: 0.67 },
      ],
      top_features: [
        { name: 'Средняя зарплата', importance: 0.31 },
        { name: 'Число навыков', importance: 0.22 },
        { name: 'Доля удалённых вакансий', importance: 0.17 },
        { name: 'Длина описания', importance: 0.11 },
        { name: 'Доля вакансий с опытом более 3 лет', importance: 0.07 },
      ],
    },
    model_scores: modelScores(),
    favorite_rate: { reference_share: 0.28, max_drop: 0.05, days: favoriteDays(from, to) },
  };
}

export const adminHandlers = [
  route('get', '/admin/collection', () => {
    const auth = authorize('admin');
    if ('response' in auth) return auth.response;
    return HttpResponse.json(collectionDashboard(auth.db));
  }),

  route('post', '/admin/collection/runs', () => {
    const auth = authorize('admin');
    if ('response' in auth) return auth.response;
    const { db } = auth;
    if (collectionDashboard(db).is_running) {
      return err(409, 'COLLECTION_ALREADY_RUNNING', 'Сбор уже выполняется');
    }
    db.counter += 1;
    db.collection_running_id = `c-run-${db.counter}`;
    db.collection_running_until = Date.now() + mockConfig.collectionMs;
    saveDb(db);
    return HttpResponse.json({ run_id: db.collection_running_id }, { status: 202 });
  }),

  route('get', '/admin/matching-speed', () => {
    const auth = authorize('admin');
    if ('response' in auth) return auth.response;
    return HttpResponse.json(speedDashboard());
  }),

  route('get', '/admin/drift', ({ request }) => {
    const auth = authorize('admin');
    if ('response' in auth) return auth.response;
    const params = new URL(request.url).searchParams;
    const to = params.get('to') ?? TODAY;
    const from = params.get('from') ?? isoDay(-29);
    if (from > to) return err(422, 'VALIDATION_ERROR', 'Дата начала должна быть не позже даты окончания');
    return HttpResponse.json(driftDashboard(from, to));
  }),
];
