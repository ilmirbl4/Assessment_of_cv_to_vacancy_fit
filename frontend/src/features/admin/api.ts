import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../../api/client';
import { api } from '../../api/endpoints';
import type { DriftDashboard } from '../../api/types';

export const COLLECTION_KEY = ['admin', 'collection'] as const;
export const COLLECTION_POLL_MS = 3000;

/** Дашборд сбора данных; пока `is_running`, обновляется каждые 3 с. */
export function useCollection() {
  return useQuery({
    queryKey: COLLECTION_KEY,
    queryFn: () => api.adminCollection(30),
    refetchInterval: (query) => (query.state.data?.is_running ? COLLECTION_POLL_MS : false),
  });
}

/** Запуск сбора вручную; 409 COLLECTION_ALREADY_RUNNING обрабатывается вызывающим кодом. */
export function useStartCollection() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.startCollection,
    onSettled: () => client.invalidateQueries({ queryKey: COLLECTION_KEY }),
  });
}

/** Признак ошибки «сбор уже выполняется». */
export function isAlreadyRunning(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'COLLECTION_ALREADY_RUNNING';
}

/** Дашборд скорости подбора. */
export function useSpeed() {
  return useQuery({ queryKey: ['admin', 'speed'], queryFn: () => api.adminSpeed(30) });
}

/**
 * Дашборд дрейфа данных за период (без периода сервер берёт последние 30 суток).
 * @param from начало периода ГГГГ-ММ-ДД
 * @param to конец периода ГГГГ-ММ-ДД
 */
export function useDrift(from?: string, to?: string) {
  return useQuery({ queryKey: ['admin', 'drift', from ?? null, to ?? null], queryFn: () => api.adminDrift(from, to) });
}

/**
 * Есть ли предупреждение дрейфа хотя бы в одном разделе дашборда.
 * @param data данные дашборда
 */
export function hasDriftWarning(data: DriftDashboard): boolean {
  return inputsDrifted(data) || scoresDrifted(data) || favoriteRateDropped(data);
}

/** Раздел «Входные данные»: PSI выше порога или ROC-AUC выше порога. */
export function inputsDrifted(data: DriftDashboard): boolean {
  return psiExceeded(data) || rocExceeded(data);
}

/** Превышает ли какой-либо PSI порог (строго больше). */
export function psiExceeded(data: DriftDashboard): boolean {
  return data.indicators.some((i) => i.psi > data.psi_threshold);
}

/** Превышает ли ROC-AUC последнего периода порог (строго больше). */
export function rocExceeded(data: DriftDashboard): boolean {
  const last = data.adversarial.periods.at(-1);
  return last !== undefined && last.roc_auc > data.adversarial.roc_auc_threshold;
}

/** Отвергает ли тест Колмогорова — Смирнова равенство распределений оценок кросс-энкодера (p < α). */
export function scoresDrifted(data: DriftDashboard): boolean {
  return data.model_scores.p_value < data.model_scores.alpha;
}

/**
 * Сводка доли подборов с добавлением в избранное за текущий период (взвешенная по числу подборов).
 * @param data данные дашборда
 */
export function favoriteRateSummary(data: DriftDashboard) {
  const { days, reference_share, max_drop } = data.favorite_rate;
  const runs = days.reduce((sum, d) => sum + d.runs, 0);
  const withFavorite = days.reduce((sum, d) => sum + d.runs_with_favorite, 0);
  const share = runs === 0 ? null : withFavorite / runs;
  // Округление убирает погрешность вычитания дробей (0,28 − 0,23 не должно давать 0,0500…01).
  const drop = share === null ? 0 : Math.round((reference_share - share) * 10_000) / 10_000;
  return { runs, withFavorite, share, change: share === null ? null : share - reference_share, dropped: drop > max_drop };
}

/** Снизилась ли доля подборов с избранным сильнее допустимого (строго больше). */
export function favoriteRateDropped(data: DriftDashboard): boolean {
  return favoriteRateSummary(data).dropped;
}
