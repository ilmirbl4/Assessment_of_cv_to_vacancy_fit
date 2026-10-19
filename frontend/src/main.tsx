import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/index.css';
import type { SetupWorker } from 'msw/browser';
import { App } from './app/App';

// Моки хранятся только локально (в .gitignore): glob вернёт пустой объект, если папки нет.
const mockModules = import.meta.glob<{ worker: SetupWorker }>('./mocks/browser.ts');

/** Запускает MSW (если включены моки и они есть локально) и рендерит приложение. */
async function bootstrap() {
  const loadMocks = mockModules['./mocks/browser.ts'];
  if (import.meta.env.VITE_USE_MOCKS === 'true' && loadMocks) {
    const { worker } = await loadMocks();
    await worker.start({ onUnhandledRequest: 'error' });
  }
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void bootstrap();
