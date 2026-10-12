import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ExternalLink } from 'lucide-react';
import { Link, useNavigate } from 'react-router';
import { ApiError, errorMessage } from '../../api/client';
import { api } from '../../api/endpoints';
import { Alert } from '../../components/ui/Alert';
import { Button } from '../../components/ui/Button';
import { Checkbox } from '../../components/ui/Checkbox';
import { Field } from '../../components/ui/Field';
import { Input } from '../../components/ui/Input';
import { PageTitle } from '../../components/ui/PageTitle';
import { type RegisterValues, registerSchema } from '../../lib/validation';

/** Страница регистрации (`/register`). */
export function RegisterPage() {
  const navigate = useNavigate();
  const consent = useQuery({ queryKey: ['consent'], queryFn: api.consent });
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: '', password: '', confirm: '', consent: false },
  });
  const { errors } = form.formState;

  const register = useMutation({
    mutationFn: (values: RegisterValues) =>
      api.register({
        email: values.email.trim(),
        password: values.password,
        consent_accepted: true,
        consent_version: consent.data?.version ?? '',
      }),
    onSuccess: (_, values) => navigate('/register/done', { state: { email: values.email.trim() } }),
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'EMAIL_TAKEN') {
        form.setError('email', { message: 'Пользователь с таким адресом уже зарегистрирован' });
      } else if (error instanceof ApiError && error.status === 422 && error.fields.email) {
        form.setError('email', { message: error.fields.email });
      } else {
        setServerError(errorMessage(error));
      }
    },
  });

  return (
    <>
      <PageTitle title="Регистрация" />
      <p className="mt-1 text-text-muted">Подбор вакансий по вашему резюме</p>
      <form
        noValidate
        onSubmit={form.handleSubmit((values) => {
          setServerError(null);
          register.mutate(values);
        })}
        className="mt-6 flex flex-col gap-4"
      >
        <Field label="Электронная почта" error={errors.email?.message}>
          {(p) => <Input type="email" autoComplete="username" {...p} {...form.register('email')} />}
        </Field>
        <Field label="Пароль" error={errors.password?.message} hint="Не менее 8 символов, буквы и цифры">
          {(p) => <Input type="password" autoComplete="new-password" {...p} {...form.register('password')} />}
        </Field>
        <Field label="Повторите пароль" error={errors.confirm?.message}>
          {(p) => <Input type="password" autoComplete="new-password" {...p} {...form.register('confirm')} />}
        </Field>
        <Checkbox
          label="Я даю согласие на обработку персональных данных"
          error={errors.consent?.message}
          {...form.register('consent')}
          suffix={
            <Link
              to="/consent"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex shrink-0 items-center gap-1 text-primary hover:underline"
            >
              Текст
              <ExternalLink aria-hidden="true" size={14} strokeWidth={2} />
            </Link>
          }
        />
        {consent.isError ? (
          <Alert variant="danger">{errorMessage(consent.error)}</Alert>
        ) : null}
        {serverError ? <Alert variant="danger">{serverError}</Alert> : null}
        <Button type="submit" fullWidth loading={register.isPending} disabled={!consent.data}>
          Зарегистрироваться
        </Button>
      </form>
      <p className="mt-6 text-sm text-text-muted">
        Уже есть учётная запись?{' '}
        <Link to="/login" className="text-primary underline underline-offset-2">
          Войти
        </Link>
      </p>
    </>
  );
}
