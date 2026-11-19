import { HttpResponse } from 'msw';
import { route } from './common';
import { adminHandlers } from './admin';
import { authHandlers } from './auth';
import { consentHandlers } from './consent';
import { favoritesHandlers } from './favorites';
import { matchingHandlers } from './matching';
import { resumeHandlers } from './resume';

/** Все обработчики моков API. */
export const handlers = [
  route('get', '/status', () =>
    HttpResponse.json({
      phase: 'ready', database_ready: true, matching_ready: true, error: null, progress: 0, total: 0,
    }),
  ),
  ...authHandlers,
  ...consentHandlers,
  ...resumeHandlers,
  ...matchingHandlers,
  ...favoritesHandlers,
  ...adminHandlers,
];
