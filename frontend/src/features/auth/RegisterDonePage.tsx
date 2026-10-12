import { useState } from 'react';
import { Navigate, useLocation } from 'react-router';
import { errorMessage } from '../../api/client';
import { api } from '../../api/endpoints';
import { Button } from '../../components/ui/Button';
import { PageTitle } from '../../components/ui/PageTitle';
import { useToast } from '../../components/ui/Toast';

/** Страница «Проверьте почту» после регистрации (`/register/done`). */
export function RegisterDonePage() {
  const location = useLocation();
  const toast = useToast();
  const [sending, setSending] = useState(false);
  const email = (location.state as { email?: string } | null)?.email;
  if (!email) return <Navigate to="/register" replace />;

  async function resend() {
    setSending(true);
    try {
      await api.resendConfirmation(email as string);
      toast('Письмо отправлено повторно');
    } catch (e) {
      toast(errorMessage(e), 'danger');
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <PageTitle title="Проверьте почту" />
      <p className="mt-4">
        Мы отправили письмо на <span data-user-content className="font-medium">{email}</span>. Перейдите по ссылке из
        письма, чтобы подтвердить адрес. До подтверждения вход невозможен.
      </p>
      <Button variant="secondary" className="mt-6" fullWidth loading={sending} onClick={() => void resend()}>
        Отправить письмо повторно
      </Button>
    </>
  );
}
