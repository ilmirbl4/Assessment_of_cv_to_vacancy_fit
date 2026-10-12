/**
 * Склеивает CSS-классы, отбрасывая пустые значения.
 * @param parts строки классов, false, null или undefined
 */
export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}
