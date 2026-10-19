import { useEffect, useRef, useState } from 'react';
import { CheckCircle, FileText } from 'lucide-react';
import { Link } from 'react-router';
import { ApiError, errorMessage } from '../../api/client';
import { Alert } from '../../components/ui/Alert';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Dialog } from '../../components/ui/Dialog';
import { FileDropzone } from '../../components/ui/FileDropzone';
import { LoadingRegion } from '../../components/ui/LoadingRegion';
import { Skeleton } from '../../components/ui/Skeleton';
import { Spinner } from '../../components/ui/Spinner';
import { QueryErrorView } from '../../components/layout/QueryErrorView';
import { formatDateTime } from '../../lib/format';
import { validateResumeFile } from '../../lib/validation';
import { GIVE_UP_AFTER_MS, SLOW_AFTER_MS, useDeleteResume, useResume, useUploadResume } from './api';

const UPLOAD_ERRORS: Record<string, string> = {
  FILE_TOO_LARGE: 'Размер файла не должен превышать 5 МБ',
  UNSUPPORTED_FORMAT: 'Допустимы только файлы DOCX или PDF',
  PDF_NO_TEXT_LAYER: 'В файле нет текстового слоя. Загрузите PDF с выделяемым текстом или DOCX.',
};

/** Секция «Резюме» личного кабинета: загрузка, замена, удаление, статус обработки. */
export function ResumeSection() {
  const [timers, setTimers] = useState({ key: '', slow: false, stopped: false });
  const [attempt, setAttempt] = useState(0);
  const stopPolling = useRef(false);
  const resume = useResume(stopPolling);
  const upload = useUploadResume();
  const remove = useDeleteResume();
  const [fileError, setFileError] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const replaceInput = useRef<HTMLInputElement>(null);

  const status = resume.data?.status;
  const key = `${resume.data?.uploaded_at ?? ''}#${attempt}`;
  useEffect(() => {
    if (status !== 'processing') return;
    stopPolling.current = false;
    const slowTimer = setTimeout(() => setTimers({ key, slow: true, stopped: false }), SLOW_AFTER_MS);
    const stopTimer = setTimeout(() => {
      stopPolling.current = true;
      setTimers({ key, slow: true, stopped: true });
    }, GIVE_UP_AFTER_MS);
    return () => {
      clearTimeout(slowTimer);
      clearTimeout(stopTimer);
    };
  }, [status, key]);
  const slow = timers.key === key && timers.slow;
  const pollingStopped = timers.key === key && timers.stopped;

  function send(file: File) {
    setFileError(null);
    upload.mutate(file, {
      onError: (e) =>
        setFileError(e instanceof ApiError ? (UPLOAD_ERRORS[e.code] ?? e.message) : errorMessage(e)),
    });
  }

  /** Проверяет файл на клиенте; запрос уходит только для допустимого файла. */
  function choose(file: File, needConfirm: boolean) {
    const problem = validateResumeFile(file);
    if (problem) {
      setFileError(problem);
      return;
    }
    if (needConfirm) setPendingFile(file);
    else send(file);
  }

  function confirmReplace() {
    const file = pendingFile;
    setPendingFile(null);
    if (file) send(file);
  }

  if (resume.isPending) {
    return (
      <Card title="Резюме">
        <LoadingRegion className="flex flex-col gap-3">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-4 w-1/3" />
        </LoadingRegion>
      </Card>
    );
  }
  if (resume.isError) {
    return (
      <Card title="Резюме">
        <QueryErrorView error={resume.error} onRetry={() => void resume.refetch()} />
      </Card>
    );
  }

  const data = resume.data;
  return (
    <Card title="Резюме">
      {fileError ? (
        <Alert variant="danger" className="mb-4">
          {fileError}
        </Alert>
      ) : null}

      {!data ? (
        <FileDropzone loading={upload.isPending} onFile={(f) => choose(f, false)} />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 items-start gap-3">
              <FileText aria-hidden="true" size={24} strokeWidth={2} className="mt-0.5 shrink-0 text-text-muted" />
              <div className="min-w-0">
                <p data-user-content className="truncate font-medium" title={data.file_name}>
                  {data.file_name}
                </p>
                <p className="text-sm text-text-muted">Загружено {formatDateTime(data.uploaded_at)}</p>
              </div>
            </div>
            <div className="flex shrink-0 gap-3">
              <Button variant="secondary" loading={upload.isPending} onClick={() => replaceInput.current?.click()}>
                Заменить резюме
              </Button>
              <Button variant="secondary" onClick={() => setDeleteOpen(true)}>
                Удалить резюме
              </Button>
            </div>
          </div>

          {data.status === 'processing' && !pollingStopped ? (
            <div role="status" className="flex items-center gap-3 text-text-muted">
              <Spinner size={20} className="text-primary" />
              <span>
                {slow
                  ? 'Обработка занимает больше обычного…'
                  : 'Обрабатываем резюме… Обычно это занимает до 30 секунд.'}
              </span>
            </div>
          ) : null}
          {data.status === 'processing' && pollingStopped ? (
            <Alert
              variant="danger"
              actions={
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    stopPolling.current = false;
                    setAttempt((n) => n + 1);
                    void resume.refetch();
                  }}
                >
                  Проверить снова
                </Button>
              }
            >
              Обработка резюме занимает слишком много времени.
            </Alert>
          ) : null}
          {data.status === 'ready' ? (
            <p role="status" className="flex items-center gap-2 text-success">
              <CheckCircle aria-hidden="true" size={20} strokeWidth={2} className="shrink-0" />
              <span>
                Резюме обработано и готово к подбору.{' '}
                <Link to="/" className="font-medium text-primary underline underline-offset-2">
                  Подобрать вакансии
                </Link>
              </span>
            </p>
          ) : null}
          {data.status === 'failed' ? (
            <Alert variant="danger">
              {data.error_message ?? 'Не удалось обработать файл.'} Загрузите другой файл.
            </Alert>
          ) : null}
        </div>
      )}

      <input
        ref={replaceInput}
        type="file"
        accept=".docx,.pdf"
        className="hidden"
        aria-label="Новый файл резюме"
        tabIndex={-1}
        data-testid="resume-replace-input"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = '';
          if (file) choose(file, true);
        }}
      />

      <Dialog
        open={pendingFile !== null}
        onClose={() => setPendingFile(null)}
        title="Заменить резюме?"
        description="Новое резюме заменит текущее. Продолжить?"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPendingFile(null)}>
              Отмена
            </Button>
            <Button onClick={confirmReplace}>Заменить резюме</Button>
          </>
        }
      />
      <Dialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        busy={remove.isPending}
        title="Удалить резюме?"
        description="Удалить резюме? Результаты подбора вакансий тоже будут удалены."
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteOpen(false)} disabled={remove.isPending}>
              Отмена
            </Button>
            <Button
              variant="danger"
              loading={remove.isPending}
              onClick={() => remove.mutate(undefined, { onSettled: () => setDeleteOpen(false) })}
            >
              Удалить резюме
            </Button>
          </>
        }
      />
    </Card>
  );
}
