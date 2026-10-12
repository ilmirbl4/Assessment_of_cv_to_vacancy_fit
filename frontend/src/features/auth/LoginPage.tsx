import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { ApiError } from '../../api/client';
import { api } from '../../api/endpoints';
import { Alert } from '../../components/ui/Alert';
import { Button } from '../../components/ui/Button';
import { Field } from '../../components/ui/Field';
import { Input } from '../../components/ui/Input';
import { PageTitle } from '../../components/ui/PageTitle';
import { useToast } from '../../components/ui/Toast';
import { errorMessage } from '../../api/client';
import { type LoginValues, loginSchema, safeNext } from '../../lib/validation';
import { homePath, resetIntentionalExit, useLogin } from './api';

/** Страница входа (`/login`). */
export function LoginPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const login = useLogin();
  const [notConfirmed, setNotConfirmed] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [resending, setResending] = useState(false);
  const form = useForm<LoginValues>({ resolver: zodResolver(loginSchema), defaultValues: { email: '', password: '' } });
  const { errors } = form.formState;
  useEffect(() => {
    resetIntentionalExit();
  }, []);

  function onSubmit(values: LoginValues) {
    setNotConfirmed(false);
    setServerError(null);
    login.mutate(
      { email: values.email.trim(), password: values.password },
      {
        onSuccess: (user) => navigate(safeNext(params.get('next')) ?? homePath(user.role), { replace: true }),
        onError: (error) => {
          if (error instanceof ApiError && error.code === 'EMAIL_NOT_CONFIRMED') setNotConfirmed(true);
          else if (error instanceof ApiError && error.code === 'INVALID_CREDENTIALS') {
            setServerError('Неверный адрес электронной почты или пароль');
          } else setServerError(errorMessage(error));
        },
      },
    );
  }

  async function resend() {
    setResending(true);
    try {
      await api.resendConfirmation(form.getValues('email').trim());
      toast('Письмо отправлено повторно');
    } catch (e) {
      toast(errorMessage(e), 'danger');
    } finally {
      setResending(false);
    }
  }

  return (
    <>
      <PageTitle title="Вход" />
      <p className="mt-1 text-text-muted">Войдите, чтобы подобрать вакансии по вашему резюме</p>
      <form noValidate onSubmit={form.handleSubmit(onSubmit)} className="mt-6 flex flex-col gap-4">
        <Field label="Электронная почта" error={errors.email?.message}>
          {(p) => <Input type="email" autoComplete="username" {...p} {...form.register('email')} />}
        </Field>
        <Field label="Пароль" error={errors.password?.message}>
          {(p) => <Input type="password" autoComplete="current-password" {...p} {...form.register('password')} />}
        </Field>
        {notConfirmed ? (
          <Alert
            variant="danger"
            actions={
              <Button variant="secondary" size="sm" loading={resending} onClick={() => void resend()}>
                Отправить письмо повторно
              </Button>
            }
          >
            Адрес электронной почты не подтверждён. Перейдите по ссылке из письма.
          </Alert>
        ) : null}
        {serverError ? <Alert variant="danger">{serverError}</Alert> : null}
        <Button type="submit" fullWidth loading={login.isPending}>
          Войти
        </Button>
      </form>
      <div className="mt-6 flex flex-col gap-2 text-sm">
        <Link to="/forgot-password" className="text-primary hover:underline">
          Забыли пароль?
        </Link>
        <p className="text-text-muted">
          Нет учётной записи?{' '}
          <Link to="/register" className="text-primary underline underline-offset-2">
            Зарегистрироваться
          </Link>
        </p>
      </div>
    </>
  );
}
