import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { Link } from 'react-router';
import { errorMessage } from '../../api/client';
import { api } from '../../api/endpoints';
import { Alert } from '../../components/ui/Alert';
import { Button } from '../../components/ui/Button';
import { Field } from '../../components/ui/Field';
import { Input } from '../../components/ui/Input';
import { PageTitle } from '../../components/ui/PageTitle';
import { type ForgotValues, forgotSchema } from '../../lib/validation';

/** Запрос ссылки для восстановления пароля (`/forgot-password`). */
export function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const form = useForm<ForgotValues>({ resolver: zodResolver(forgotSchema), defaultValues: { email: '' } });
  const request = useMutation({
    mutationFn: (values: ForgotValues) => api.requestPasswordReset(values.email.trim()),
    onSuccess: () => setSent(true),
  });

  return (
    <>
      <PageTitle title="Восстановление пароля" />
      {sent ? (
        <div className="mt-6 flex flex-col gap-4">
          <Alert variant="success">
            Если такой адрес зарегистрирован, мы отправили на него письмо со ссылкой для восстановления пароля
          </Alert>
          <Link to="/login" className="text-sm text-primary hover:underline">
            Вернуться ко входу
          </Link>
        </div>
      ) : (
        <>
          <p className="mt-1 text-text-muted">Укажите адрес электронной почты, и мы пришлём ссылку для смены пароля</p>
          <form noValidate onSubmit={form.handleSubmit((v) => request.mutate(v))} className="mt-6 flex flex-col gap-4">
            <Field label="Электронная почта" error={form.formState.errors.email?.message}>
              {(p) => <Input type="email" autoComplete="username" {...p} {...form.register('email')} />}
            </Field>
            {request.isError ? <Alert variant="danger">{errorMessage(request.error)}</Alert> : null}
            <Button type="submit" fullWidth loading={request.isPending}>
              Отправить ссылку
            </Button>
          </form>
          <Link to="/login" className="mt-6 inline-block text-sm text-primary hover:underline">
            Вернуться ко входу
          </Link>
        </>
      )}
    </>
  );
}
