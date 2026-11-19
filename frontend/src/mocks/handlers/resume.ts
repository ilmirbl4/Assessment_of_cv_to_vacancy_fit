import { HttpResponse } from 'msw';
import type { Resume } from '../../api/types';
import { type DbState, mockConfig, saveDb } from '../db';
import { SKILL_POOL } from '../seed';
import { authorize, err, noContent, route } from './common';

/**
 * Возвращает резюме пользователя с вычисленным статусом (processing → ready/failed по времени).
 * @param db состояние моков
 * @param userId идентификатор пользователя
 */
export function currentResume(db: DbState, userId: string): Resume | null {
  const stored = db.resumes[userId];
  if (!stored) return null;
  const processing = Date.now() < stored.ready_at;
  const status = processing ? 'processing' : stored.outcome;
  return {
    file_name: stored.file_name,
    uploaded_at: stored.uploaded_at,
    status,
    error_message:
      status === 'failed' ? 'Не удалось прочитать текст резюме.' : null,
  };
}

export const resumeHandlers = [
  route('get', '/resume', () => {
    const auth = authorize('seeker');
    if ('response' in auth) return auth.response;
    const resume = currentResume(auth.db, auth.user.id);
    if (!resume) return err(404, 'RESUME_NOT_FOUND', 'Резюме не загружено');
    return HttpResponse.json(resume);
  }),

  route('put', '/resume', async ({ request }) => {
    const auth = authorize('seeker');
    if ('response' in auth) return auth.response;
    const form = await request.formData();
    const file = form.get('file');
    if (!(file instanceof Blob)) return err(422, 'VALIDATION_ERROR', 'Файл не передан');
    const name = (file as File).name ?? '';
    if (!/\.(docx|pdf)$/i.test(name)) return err(415, 'UNSUPPORTED_FORMAT', 'Допустимы только файлы DOCX или PDF');
    if (file.size > 5 * 1024 * 1024) return err(413, 'FILE_TOO_LARGE', 'Размер файла не должен превышать 5 МБ');
    if (name.toLowerCase().includes('scan')) {
      return err(422, 'PDF_NO_TEXT_LAYER', 'В файле нет текстового слоя. Загрузите PDF с выделяемым текстом или DOCX.');
    }
    const shift = [...name].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % 10;
    auth.db.resumes[auth.user.id] = {
      file_name: name,
      uploaded_at: new Date().toISOString(),
      ready_at: Date.now() + mockConfig.resumeProcessingMs,
      outcome: name.toLowerCase().includes('broken') ? 'failed' : 'ready',
      skills: SKILL_POOL.slice(shift, shift + 20),
    };
    saveDb(auth.db);
    const resume = currentResume(auth.db, auth.user.id) as Resume;
    return HttpResponse.json(resume, { status: 202 });
  }),

  route('delete', '/resume', () => {
    const auth = authorize('seeker');
    if ('response' in auth) return auth.response;
    delete auth.db.resumes[auth.user.id];
    delete auth.db.runs[auth.user.id];
    saveDb(auth.db);
    return noContent();
  }),
];
