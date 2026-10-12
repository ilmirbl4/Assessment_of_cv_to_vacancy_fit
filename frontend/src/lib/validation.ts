import { z } from 'zod';
import type { MatchFilters } from '../api/types';

/** Zod-схемы и проверки форм (FRONTEND_INSTRUCTIONS.md, раздел 6.3; ТЗ п. 4.2.1). */

export const MSG = {
  required: 'Заполните это поле',
  email: 'Введите корректный адрес электронной почты',
  password: 'Пароль должен содержать не менее 8 символов, буквы и цифры',
  passwordMismatch: 'Пароли не совпадают',
  consent: 'Для регистрации необходимо дать согласие на обработку персональных данных',
  fileFormat: 'Допустимы только файлы DOCX или PDF',
  fileSize: 'Размер файла не должен превышать 5 МБ',
  salary: 'Введите целое число от 0 до 10\u00A0000\u00A0000', // неразрывные пробелы: число не рвётся при переносе
  periodOrder: 'Дата начала должна быть не позже даты окончания',
  periodFuture: 'Дата окончания не может быть в будущем',
} as const;

export const MAX_RESUME_BYTES = 5 * 1024 * 1024;
export const MAX_SALARY = 10_000_000;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** Схема поля «Электронная почта». */
export const emailSchema = z
  .string()
  .trim()
  .refine((v) => EMAIL_RE.test(v), { message: MSG.email });

/** Схема пароля: от 8 символов, есть буква и цифра. */
export const passwordSchema = z
  .string()
  .refine((v) => v.length >= 8 && /\p{L}/u.test(v) && /\d/.test(v), { message: MSG.password });

const nonEmpty = z.string().min(1, MSG.required);

/** Схема формы входа. */
export const loginSchema = z.object({ email: emailSchema, password: nonEmpty });
export type LoginValues = z.infer<typeof loginSchema>;

/** Схема формы регистрации. */
export const registerSchema = z
  .object({
    email: emailSchema,
    password: passwordSchema,
    confirm: z.string(),
    consent: z.boolean().refine((v) => v, { message: MSG.consent }),
  })
  .refine((v) => v.password === v.confirm, { message: MSG.passwordMismatch, path: ['confirm'] });
export type RegisterValues = z.infer<typeof registerSchema>;

/** Схема формы «Забыли пароль». */
export const forgotSchema = z.object({ email: emailSchema });
export type ForgotValues = z.infer<typeof forgotSchema>;

/** Схема формы нового пароля. */
export const resetSchema = z
  .object({ password: passwordSchema, confirm: z.string() })
  .refine((v) => v.password === v.confirm, { message: MSG.passwordMismatch, path: ['confirm'] });
export type ResetValues = z.infer<typeof resetSchema>;

/**
 * Проверяет файл резюме: расширение и размер.
 * @param file объект с именем и размером в байтах
 * @returns текст ошибки или null, если файл допустим
 */
export function validateResumeFile(file: { name: string; size: number }): string | null {
  if (!/\.(docx|pdf)$/i.test(file.name)) return MSG.fileFormat;
  if (file.size > MAX_RESUME_BYTES) return MSG.fileSize;
  return null;
}

/** Схема поля «Минимальная зарплата» (строка: пусто или целое 0..10 000 000). */
export const minSalarySchema = z
  .string()
  .trim()
  .refine((v) => v === '' || (/^\d+$/.test(v) && Number(v) <= MAX_SALARY), { message: MSG.salary });

/** Схема формы фильтров подбора. */
export const filtersSchema = z.object({
  region_code: z.string(),
  min_salary: minSalarySchema,
  only_with_salary: z.boolean(),
  employment_type: z.string(),
  schedule: z.string(),
  experience: z.string(),
});
export type FiltersFormValues = z.infer<typeof filtersSchema>;

/** Пустые значения формы фильтров. */
export const emptyFilters: FiltersFormValues = {
  region_code: '',
  min_salary: '',
  only_with_salary: false,
  employment_type: '',
  schedule: '',
  experience: '',
};

/**
 * Преобразует значения формы фильтров в тело запроса.
 * @param values значения формы (после валидации)
 */
export function toMatchFilters(values: FiltersFormValues): MatchFilters {
  const salary = values.min_salary.trim();
  return {
    region_code: values.region_code || null,
    min_salary: salary === '' ? null : Number(salary),
    only_with_salary: values.only_with_salary,
    employment_type: values.employment_type || null,
    schedule: values.schedule || null,
    experience: values.experience || null,
  };
}

/**
 * Преобразует фильтры ответа сервера в значения формы.
 * @param filters фильтры подбора
 */
export function fromMatchFilters(filters: MatchFilters): FiltersFormValues {
  return {
    region_code: filters.region_code ?? '',
    min_salary: filters.min_salary === null ? '' : String(filters.min_salary),
    only_with_salary: filters.only_with_salary,
    employment_type: filters.employment_type ?? '',
    schedule: filters.schedule ?? '',
    experience: filters.experience ?? '',
  };
}

/**
 * Создаёт схему периода дрейфа.
 * @param today сегодняшняя дата ГГГГ-ММ-ДД
 */
export function makePeriodSchema(today: string) {
  return z
    .object({ from: nonEmpty, to: nonEmpty })
    .superRefine((v, ctx) => {
      if (v.from > v.to) ctx.addIssue({ code: 'custom', message: MSG.periodOrder, path: ['from'] });
      if (v.to > today) ctx.addIssue({ code: 'custom', message: MSG.periodFuture, path: ['to'] });
    });
}

/**
 * Проверяет безопасность адреса возврата `next` (защита от open redirect).
 * @param next значение параметра или null
 * @returns строка, если адрес внутренний, иначе null
 */
export function safeNext(next: string | null): string | null {
  if (next && next.startsWith('/') && !next.startsWith('//') && !next.includes('\\')) return next;
  return null;
}
