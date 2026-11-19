import { HttpResponse } from 'msw';
import { emailSchema, passwordSchema } from '../../lib/validation';
import { CONSENT } from './consent';
import { authorize, err, noContent, route } from './common';
import { loadDb, saveDb, setSessionEmail } from '../db';

const VALID_TOKEN = 'valid-token';

export const authHandlers = [
  route('get', '/auth/me', () => {
    const auth = authorize();
    if ('response' in auth) return auth.response;
    const { id, email, role } = auth.user;
    return HttpResponse.json({ id, email, role });
  }),

  route('post', '/auth/register', async ({ request }) => {
    const body = (await request.json()) as {
      email?: string;
      password?: string;
      consent_accepted?: boolean;
      consent_version?: string;
    };
    const fields: Record<string, string> = {};
    if (!emailSchema.safeParse(body.email ?? '').success) fields.email = 'Введите корректный адрес электронной почты';
    if (!passwordSchema.safeParse(body.password ?? '').success) {
      fields.password = 'Пароль должен содержать не менее 8 символов, буквы и цифры';
    }
    if (body.consent_accepted !== true || body.consent_version !== CONSENT.version) {
      fields.consent_accepted = 'Для регистрации необходимо дать согласие на обработку персональных данных';
    }
    if (Object.keys(fields).length > 0) return err(422, 'VALIDATION_ERROR', 'Проверьте введённые данные', fields);

    const db = loadDb();
    const email = (body.email ?? '').trim().toLowerCase();
    if (db.users.some((u) => u.email.toLowerCase() === email)) {
      return err(409, 'EMAIL_TAKEN', 'Пользователь с таким адресом уже зарегистрирован');
    }
    db.counter += 1;
    db.users.push({
      id: `u-new-${db.counter}`,
      email,
      password: body.password ?? '',
      role: 'seeker',
      confirmed: false,
      via_ui: true,
    });
    saveDb(db);
    return HttpResponse.json({}, { status: 201 });
  }),

  route('post', '/auth/login', async ({ request }) => {
    const body = (await request.json()) as { email?: string; password?: string };
    const db = loadDb();
    const email = (body.email ?? '').trim().toLowerCase();
    const user = db.users.find((u) => u.email.toLowerCase() === email);
    if (!user || user.password !== body.password) {
      return err(401, 'INVALID_CREDENTIALS', 'Неверный адрес электронной почты или пароль');
    }
    if (!user.confirmed) return err(403, 'EMAIL_NOT_CONFIRMED', 'Адрес электронной почты не подтверждён');
    setSessionEmail(user.email);
    return HttpResponse.json({ id: user.id, email: user.email, role: user.role });
  }),

  route('post', '/auth/logout', () => {
    const auth = authorize();
    if (!('response' in auth)) {
      delete auth.db.runs[auth.user.id]; // результат подбора не переживает выход
      saveDb(auth.db);
    }
    setSessionEmail(null);
    return noContent();
  }),

  route('post', '/auth/confirm-email', async ({ request }) => {
    const body = (await request.json()) as { token?: string };
    if (body.token !== VALID_TOKEN) return err(400, 'TOKEN_INVALID', 'Ссылка недействительна или устарела');
    const db = loadDb();
    db.users.filter((u) => u.via_ui).forEach((u) => (u.confirmed = true));
    saveDb(db);
    return HttpResponse.json({});
  }),

  route('post', '/auth/resend-confirmation', () => HttpResponse.json({}, { status: 202 })),

  route('post', '/auth/password-reset/request', async ({ request }) => {
    const body = (await request.json()) as { email?: string };
    const db = loadDb();
    db.reset_email = (body.email ?? '').trim().toLowerCase();
    saveDb(db);
    return HttpResponse.json({}, { status: 202 });
  }),

  route('post', '/auth/password-reset/confirm', async ({ request }) => {
    const body = (await request.json()) as { token?: string; new_password?: string };
    if (body.token !== VALID_TOKEN) return err(400, 'TOKEN_INVALID', 'Ссылка недействительна или устарела');
    if (!passwordSchema.safeParse(body.new_password ?? '').success) {
      return err(422, 'VALIDATION_ERROR', 'Проверьте введённые данные', {
        new_password: 'Пароль должен содержать не менее 8 символов, буквы и цифры',
      });
    }
    const db = loadDb();
    const user = db.users.find((u) => u.email.toLowerCase() === db.reset_email);
    if (user) user.password = body.new_password ?? user.password;
    saveDb(db);
    return HttpResponse.json({});
  }),

  route('delete', '/account', () => {
    const auth = authorize();
    if ('response' in auth) return auth.response;
    const { db, user } = auth;
    db.users = db.users.filter((u) => u.id !== user.id);
    delete db.resumes[user.id];
    delete db.favorites[user.id];
    delete db.runs[user.id];
    saveDb(db);
    setSessionEmail(null);
    return noContent();
  }),
];
