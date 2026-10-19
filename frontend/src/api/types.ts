/** Типы контракта REST API (FRONTEND_INSTRUCTIONS.md, раздел 4.2). */

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    fields?: Record<string, string>;
  };
}

export type Role = 'seeker' | 'admin';
export interface User {
  id: string;
  email: string;
  role: Role;
}

export interface Option {
  code: string;
  name: string;
}
export interface Dictionaries {
  regions: Option[];
  employment_types: Option[];
  schedules: Option[];
  experience: Option[];
}

export type ResumeStatus = 'processing' | 'ready' | 'failed';
export interface Resume {
  file_name: string;
  uploaded_at: string;
  status: ResumeStatus;
  error_message: string | null;
}

export interface MatchFilters {
  region_code: string | null;
  min_salary: number | null;
  only_with_salary: boolean;
  employment_type: string | null;
  schedule: string | null;
  experience: string | null;
}

export interface VacancyCard {
  id: string;
  title: string;
  salary_from: number | null;
  salary_to: number | null;
  employer_name: string;
  published_at: string;
  match_percent: number;
}

export interface MatchPage {
  run_id: string;
  created_at: string;
  filters: MatchFilters;
  total: number;
  page: number;
  page_size: 10;
  total_pages: number;
  items: VacancyCard[];
}

/** Вердикт кросс-энкодера по паре «требование — фраза резюме». */
export type RequirementStatus = 'covered' | 'partially_covered' | 'not_covered';
export interface Requirement {
  number: number;
  text: string;
  status: RequirementStatus;
  /** Фраза резюме, которой кросс-энкодер покрывает требование; null для `not_covered`. */
  resume_quote: string | null;
}

export interface VacancyDetail extends Omit<VacancyCard, 'match_percent'> {
  match_percent: number | null;
  region_name: string;
  source_url: string;
  is_active: boolean;
  is_favorite: boolean;
  source_fields: { label: string; value: string }[];
  requirements: Requirement[];
}

export interface FavoriteItem {
  vacancy: Omit<VacancyCard, 'match_percent'>;
  is_active: boolean;
  added_at: string;
}

export type CollectionStatus = 'running' | 'success' | 'partial' | 'failed';
export interface CollectionRun {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: CollectionStatus;
  new_count: number;
  updated_count: number;
  deactivated_count: number;
  error_count: number;
}
export interface CollectionDashboard {
  active_vacancies_total: number;
  is_running: boolean;
  runs: CollectionRun[];
}

export interface SpeedDay {
  date: string;
  avg_ms: number;
  p95_ms: number;
  count: number;
}
export interface SpeedDashboard {
  days: SpeedDay[];
}

export interface DistributionBin {
  bin: string;
  share: number;
}
export type DriftEntity = 'vacancies' | 'resumes';
export interface DriftIndicator {
  key: 'skills_per_vacancy' | 'professional_area' | 'vacancy_embeddings' | 'resume_embeddings';
  name: string;
  /** Чьё распределение сравнивается: вакансий или резюме. */
  entity: DriftEntity;
  /** Что откладывается по оси корзин (для эмбеддингов — косинусное расстояние до центроида эталона). */
  bins_label: string;
  psi: number;
  reference: DistributionBin[];
  current: DistributionBin[];
}

/** Двухвыборочный тест Колмогорова — Смирнова для оценок кросс-энкодера. */
export interface ScoreDrift {
  /** Статистика D — наибольшее расхождение эмпирических функций распределения. */
  statistic: number;
  p_value: number;
  /** Уровень значимости: предупреждение, если p_value < alpha. */
  alpha: number;
  reference_size: number;
  current_size: number;
  /** Гистограмма оценок (корзины по 0,1 на отрезке [0; 1]). */
  reference: DistributionBin[];
  current: DistributionBin[];
}

export interface FavoriteRateDay {
  date: string;
  runs: number;
  runs_with_favorite: number;
  share: number;
}
/** Доля подборов, после которых соискатель добавил хотя бы одну вакансию в избранное. */
export interface FavoriteRate {
  reference_share: number;
  /** Допустимое снижение доли относительно эталона (в долях, 0.05 = 5 п. п.). */
  max_drop: number;
  days: FavoriteRateDay[];
}

export interface DriftDashboard {
  reference_period: { from: string; to: string };
  current_period: { from: string; to: string };
  psi_threshold: number;
  indicators: DriftIndicator[];
  adversarial: {
    roc_auc_threshold: number;
    periods: { from: string; to: string; roc_auc: number }[];
    top_features: { name: string; importance: number }[];
  };
  model_scores: ScoreDrift;
  favorite_rate: FavoriteRate;
}

export interface Consent {
  version: string;
  text: string;
  published_at: string;
}
