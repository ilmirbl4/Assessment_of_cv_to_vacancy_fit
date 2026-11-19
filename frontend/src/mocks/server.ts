import { setupServer } from 'msw/node';
import { handlers } from './handlers';

/** Сервер моков для Vitest. */
export const server = setupServer(...handlers);
