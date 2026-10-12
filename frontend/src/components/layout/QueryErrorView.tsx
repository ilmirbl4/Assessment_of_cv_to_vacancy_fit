import { ApiError, errorMessage } from '../../api/client';
import { ForbiddenView } from '../../pages/ForbiddenPage';
import { Alert } from '../ui/Alert';
import { Button } from '../ui/Button';

/**
 * Ошибка загрузки: 403 → страница «Доступ запрещён», иначе Alert с кнопкой «Повторить».
 * @param error ошибка запроса
 * @param onRetry повторить запрос
 */
export function QueryErrorView({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  if (error instanceof ApiError && error.status === 403) return <ForbiddenView />;
  return (
    <Alert
      variant="danger"
      actions={
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Повторить
        </Button>
      }
    >
      {errorMessage(error)}
    </Alert>
  );
}
