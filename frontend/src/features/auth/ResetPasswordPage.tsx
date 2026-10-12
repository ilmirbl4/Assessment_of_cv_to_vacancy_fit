import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import { ApiError, errorMessage } from '../../api/client';
import { api } from '../../api/endpoints';
import { Alert } from '../../components/ui/Alert';
import { Button } from '../../components/ui/Button';
import { ButtonLink } from '../../components/ui/ButtonLink';
import { Field } from '../../components/ui/Field';
import { Input } from '../../components/ui/Input';
import { PageTitle } from '../../components/ui/PageTitle';
import { type ResetValues, resetSchema } from '../../lib/validation';

const INVALID_LINK = 'Ссылка недействительна или устарела';

/** Установка нового пароля по ссылке из письма (`/reset-password?token=`). */
export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [done, setDone] = useState(false);
  const [serverError, setServerError] = useState<string | null>(token ? null : INVALID_LINK);
  const form = useForm<ResetValues>({ resolver: zodResolver(resetSchema), defaultValues: { password: '', confirm: '' } });
  const { errors } = form.formState;

  const reset = useMutation({
    mutationFn: (values: ResetValues) => api.confirmPasswordReset({ token, new_password: values.password }),
    onSuccess: () => setDone(true),
    onError: (error) =>
      setServerError(error instanceof ApiError && error.code === 'TOKEN_INVALID' ? INVALID_LINK : errorMessage(error)),
  });

  if (done) {
    return (
      <>
        <PageTitle title="Пароль изменён" />
        <p className="mt-2 text-text-muted">Теперь можно войти с новым паролем</p>
        <ButtonLink to="/login" className="mt-6 w-full">
          Войти
        </ButtonLink>
      </>
    );
  }

  return (
    <>
      <PageTitle title="Новый пароль" />
      <form
        noValidate
        onSubmit={form.handleSubmit((v) => {
          setServerError(null);
          reset.mutate(v);
        })}
        className="mt-6 flex flex-col gap-4"
      >
        <Field label="Новый пароль" error={errors.password?.message} hint="Не менее 8 символов, буквы и цифры">
          {(p) => <Input type="password" autoComplete="new-password" {...p} {...form.register('password')} />}
        </Field>
        <Field label="Повторите пароль" error={errors.confirm?.message}>
          {(p) => <Input type="password" autoComplete="new-password" {...p} {...form.register('confirm')} />}
        </Field>
        {serverError ? <Alert variant="danger">{serverError}</Alert> : null}
        <Button type="submit" fullWidth loading={reset.isPending} disabled={!token}>
          Сохранить пароль
        </Button>
      </form>
    </>
  );
}
