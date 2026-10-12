import { useState } from 'react';
import { useNavigate } from 'react-router';
import { errorMessage } from '../../api/client';
import { Alert } from '../../components/ui/Alert';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Dialog } from '../../components/ui/Dialog';
import { Field } from '../../components/ui/Field';
import { Input } from '../../components/ui/Input';
import { useToast } from '../../components/ui/Toast';
import { useMe } from '../auth/api';
import { useDeleteAccount } from './api';

const CONFIRM_WORD = 'УДАЛИТЬ';

/** Секция «Учётная запись»: email и удаление учётной записи с подтверждением словом «УДАЛИТЬ». */
export function AccountSection() {
  const me = useMe().data;
  const navigate = useNavigate();
  const toast = useToast();
  const remove = useDeleteAccount();
  const [open, setOpen] = useState(false);
  const [word, setWord] = useState('');

  function close() {
    setOpen(false);
    setWord('');
  }

  return (
    <Card title="Учётная запись">
      <p>
        <span className="text-text-muted">Электронная почта: </span>
        <span data-user-content>{me?.email}</span>
      </p>
      <div className="mt-4 flex items-center justify-between gap-4">
        <p className="text-sm text-text-muted">Удаление учётной записи необратимо.</p>
        <Button variant="danger" onClick={() => setOpen(true)}>
          Удалить учётную запись
        </Button>
      </div>
      <Dialog
        open={open}
        onClose={close}
        busy={remove.isPending}
        title="Удалить учётную запись?"
        description="Учётная запись, резюме и все персональные данные будут удалены безвозвратно."
        footer={
          <>
            <Button variant="secondary" onClick={close} disabled={remove.isPending}>
              Отмена
            </Button>
            <Button
              variant="danger"
              disabled={word !== CONFIRM_WORD}
              loading={remove.isPending}
              onClick={() =>
                remove.mutate(undefined, {
                  onSuccess: () => {
                    navigate('/login', { replace: true });
                    toast('Учётная запись удалена');
                  },
                })
              }
            >
              Удалить учётную запись
            </Button>
          </>
        }
      >
        <Field label={`Для подтверждения введите слово ${CONFIRM_WORD}`}>
          {(p) => <Input value={word} onChange={(e) => setWord(e.target.value)} autoComplete="off" {...p} />}
        </Field>
        {remove.isError ? (
          <Alert variant="danger" className="mt-3">
            {errorMessage(remove.error)}
          </Alert>
        ) : null}
      </Dialog>
    </Card>
  );
}
