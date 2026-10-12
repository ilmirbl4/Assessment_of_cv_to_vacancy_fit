import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import { ApiError, errorMessage } from '../../api/client';
import { api } from '../../api/endpoints';
import { Alert } from '../../components/ui/Alert';
import { Button } from '../../components/ui/Button';
import { ButtonLink } from '../../components/ui/ButtonLink';
import { PageTitle } from '../../components/ui/PageTitle';
import { Spinner } from '../../components/ui/Spinner';

/** Подтверждение адреса по ссылке из письма (`/confirm-email?token=`); запрос уходит автоматически. */
export function ConfirmEmailPage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const query = useQuery({
    queryKey: ['confirm-email', token],
    queryFn: async () => {
      await api.confirmEmail(token);
      return true;
    },
    retry: false,
    staleTime: Infinity,
  });

  if (query.isPending) {
    return (
      <>
        <PageTitle title="Подтверждение адреса" />
        <div role="status" className="mt-4 flex items-center gap-3 text-text-muted">
          <Spinner size={20} />
          <span>Подтверждаем адрес…</span>
        </div>
      </>
    );
  }
  if (query.isError) {
    const invalid = query.error instanceof ApiError && query.error.status === 400;
    return (
      <>
        <PageTitle title="Подтверждение адреса" />
        <div className="mt-4">
          <Alert
            variant="danger"
            actions={
              invalid ? undefined : (
                <Button variant="secondary" size="sm" onClick={() => void query.refetch()}>
                  Повторить
                </Button>
              )
            }
          >
            {invalid ? 'Ссылка недействительна или устарела' : errorMessage(query.error)}
          </Alert>
        </div>
      </>
    );
  }
  return (
    <>
      <PageTitle title="Адрес подтверждён" />
      <p className="mt-2 text-text-muted">Теперь можно войти в систему</p>
      <ButtonLink to="/login" className="mt-6 w-full">
        Войти
      </ButtonLink>
    </>
  );
}
