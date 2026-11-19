import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

/** Service worker с моками API для режима разработки и e2e. */
export const worker = setupWorker(...handlers);
