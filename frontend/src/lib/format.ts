/** Функции форматирования чисел, денег и дат (FRONTEND_INSTRUCTIONS.md, раздел 6.2). */

const NBSP = ' ';

/**
 * Форматирует целое число с неразрывным пробелом как разделителем тысяч.
 * @param value число
 */
export function formatNumber(value: number): string {
  return String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
}

/**
 * Форматирует дробное число по правилам ru-RU (запятая, два знака): 0,27.
 * @param value число
 */
export function formatDecimal(value: number): string {
  return value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * Форматирует число без лишних нулей по правилам ru-RU (до двух знаков): 0,6.
 * @param value число
 */
export function formatRatio(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
}

/**
 * Форматирует вилку зарплаты: «от», «до», диапазон, одно значение или «Зарплата не указана».
 * @param from нижняя граница в рублях или null
 * @param to верхняя граница в рублях или null
 */
export function formatSalary(from: number | null, to: number | null): string {
  if (from === null && to === null) return 'Зарплата не указана';
  if (from !== null && to !== null) {
    if (from === to) return `${formatNumber(from)}${NBSP}₽`;
    return `${formatNumber(from)}${NBSP}–${NBSP}${formatNumber(to)}${NBSP}₽`;
  }
  if (from !== null) return `от${NBSP}${formatNumber(from)}${NBSP}₽`;
  return `до${NBSP}${formatNumber(to as number)}${NBSP}₽`;
}

/**
 * Преобразует дату «ГГГГ-ММ-ДД» в «ДД.ММ.ГГГГ» разбором по частям (без часовых поясов).
 * @param iso дата в формате ГГГГ-ММ-ДД
 */
export function formatDate(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return iso;
  return `${match[3]}.${match[2]}.${match[1]}`;
}

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

/**
 * Преобразует момент времени ISO 8601 в «ДД.ММ.ГГГГ ЧЧ:ММ» в часовом поясе браузера.
 * @param iso момент времени со смещением
 */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Форматирует процент: округляет и ограничивает диапазоном 0..100.
 * @param value значение в процентах
 */
export function formatPercent(value: number): string {
  const safe = Number.isFinite(value) ? value : 0;
  return `${Math.min(100, Math.max(0, Math.round(safe)))}%`;
}

/**
 * Возвращает локальную дату в формате ГГГГ-ММ-ДД.
 * @param date дата (по умолчанию — сейчас)
 */
export function toIsoDate(date: Date = new Date()): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/**
 * Сдвигает дату ГГГГ-ММ-ДД на заданное число дней.
 * @param iso исходная дата
 * @param days число дней (может быть отрицательным)
 */
export function shiftIsoDate(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number);
  return toIsoDate(new Date(y, m - 1, d + days));
}
