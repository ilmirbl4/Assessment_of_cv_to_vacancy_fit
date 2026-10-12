import { useState } from 'react';
import { FileText, Search, Trash2 } from 'lucide-react';
import { AppHeader } from '../components/layout/AppHeader';
import { PageContainer } from '../components/layout/PageContainer';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Checkbox } from '../components/ui/Checkbox';
import { Chip } from '../components/ui/Chip';
import { Combobox } from '../components/ui/Combobox';
import { Dialog } from '../components/ui/Dialog';
import { EmptyState } from '../components/ui/EmptyState';
import { Field } from '../components/ui/Field';
import { FileDropzone } from '../components/ui/FileDropzone';
import { Input } from '../components/ui/Input';
import { MatchBadge } from '../components/ui/MatchBadge';
import { PageTitle } from '../components/ui/PageTitle';
import { Pagination } from '../components/ui/Pagination';
import { ProgressBar } from '../components/ui/ProgressBar';
import { Select } from '../components/ui/Select';
import { Skeleton } from '../components/ui/Skeleton';
import { Spinner } from '../components/ui/Spinner';
import { StatCard } from '../components/ui/StatCard';
import { type StatusKind, StatusBadge } from '../components/ui/StatusBadge';
import { Table, Td, Th } from '../components/ui/Table';
import { Tabs } from '../components/ui/Tabs';
import { useToast } from '../components/ui/Toast';
import { formatNumber } from '../lib/format';

const regions = [
  { code: '77', name: 'Москва' },
  { code: '78', name: 'Санкт-Петербург' },
  { code: '16', name: 'Республика Татарстан' },
];
const statuses: StatusKind[] = ['covered', 'not_covered', 'inactive', 'running', 'success', 'partial', 'failed', 'ok', 'drift'];

/** Витрина всех UI-компонентов во всех состояниях (только в режиме разработки, маршрут `/__ui`). */
export function UiKitPage() {
  const toast = useToast();
  const [region, setRegion] = useState('');
  const [page, setPage] = useState(4);
  const [dialog, setDialog] = useState(false);

  return (
    <>
      <AppHeader />
      <PageContainer>
        <PageTitle title="Витрина компонентов" />
        <div className="mt-6 flex flex-col gap-6">
          <Card title="Кнопки">
            <div className="flex flex-wrap items-center gap-3">
              <Button>Подобрать вакансии</Button>
              <Button variant="secondary">Повторить</Button>
              <Button variant="ghost">Сбросить фильтры</Button>
              <Button variant="danger" icon={Trash2}>
                Удалить резюме
              </Button>
              <Button size="sm">Малая</Button>
              <Button loading>Загрузка</Button>
              <Button disabled>Недоступна</Button>
            </div>
          </Card>

          <Card title="Поля формы">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Электронная почта" hint="Подсказка под полем">
                {(p) => <Input type="email" {...p} />}
              </Field>
              <Field label="Пароль" error="Пароль должен содержать не менее 8 символов, буквы и цифры">
                {(p) => <Input type="password" {...p} />}
              </Field>
              <Field label="Минимальная зарплата, ₽">
                {(p) => <Input inputMode="numeric" suffix="₽" {...p} />}
              </Field>
              <Field label="Отключённое поле">{(p) => <Input disabled defaultValue="Недоступно" {...p} />}</Field>
              <Field label="Тип занятости">
                {(p) => (
                  <Select {...p}>
                    <option value="">Любой</option>
                    <option value="full">Полная занятость</option>
                  </Select>
                )}
              </Field>
              <Field label="Регион">
                {(p) => <Combobox options={regions} value={region} onChange={setRegion} allLabel="Все регионы" {...p} />}
              </Field>
              <Checkbox label="Только с указанной зарплатой" />
              <Checkbox label="Я даю согласие на обработку персональных данных" error="Необходимо согласие" />
            </div>
          </Card>

          <Card title="Бейджи">
            <div className="flex flex-wrap items-center gap-3">
              <MatchBadge percent={92} />
              <MatchBadge percent={55} />
              <MatchBadge percent={12} />
              {statuses.map((s) => (
                <StatusBadge key={s} kind={s} />
              ))}
              <Chip>Python</Chip>
              <Chip>PostgreSQL</Chip>
            </div>
            <div className="mt-4 max-w-sm">
              <ProgressBar percent={92} />
            </div>
          </Card>

          <Card title="Сообщения">
            <div className="flex flex-col gap-3">
              <Alert variant="info">Подсказка для пользователя.</Alert>
              <Alert variant="success">Действие выполнено.</Alert>
              <Alert variant="warning" title="Предупреждение">
                Обратите внимание на это сообщение.
              </Alert>
              <Alert variant="danger" actions={<Button variant="secondary" size="sm">Повторить</Button>}>
                Не удалось связаться с сервером. Проверьте подключение и повторите попытку.
              </Alert>
            </div>
          </Card>

          <Card title="Таблица">
            <Table caption="Пример таблицы">
              <thead>
                <tr>
                  <Th>Показатель</Th>
                  <Th numeric>Значение</Th>
                  <Th>Состояние</Th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <Td>Активных вакансий</Td>
                  <Td numeric>{formatNumber(104532)}</Td>
                  <Td>
                    <StatusBadge kind="ok" />
                  </Td>
                </tr>
              </tbody>
            </Table>
          </Card>

          <Card title="Пагинация и вкладки">
            <Pagination page={page} totalPages={10} onChange={setPage} />
            <div className="mt-6">
              <Tabs
                label="Пример вкладок"
                items={[
                  { to: '/__ui', label: 'Сбор данных' },
                  { to: '/consent', label: 'Скорость подбора' },
                  { to: '/login', label: 'Дрейф данных', warning: true },
                ]}
              />
            </div>
          </Card>

          <div className="grid grid-cols-3 gap-6">
            <StatCard label="Активных вакансий" value={formatNumber(104532)} />
            <Card title="Скелетон">
              <div className="flex flex-col gap-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                <Spinner size={24} className="text-primary" />
              </div>
            </Card>
            <Card title="Окна и уведомления">
              <div className="flex flex-wrap gap-3">
                <Button variant="secondary" onClick={() => setDialog(true)}>
                  Открыть окно
                </Button>
                <Button variant="secondary" onClick={() => toast('Вакансия удалена из избранного')}>
                  Показать уведомление
                </Button>
              </div>
            </Card>
          </div>

          <Card title="Пустые состояния и загрузка файла">
            <EmptyState icon={Search} title="Задайте фильтры и нажмите «Подобрать вакансии»" />
            <EmptyState icon={FileText} title="Нет резюме" description="Загрузите резюме, чтобы увидеть подходящие вакансии." />
            <FileDropzone onFile={() => undefined} />
          </Card>
        </div>
      </PageContainer>
      <Dialog
        open={dialog}
        onClose={() => setDialog(false)}
        title="Удалить резюме?"
        description="Навыки, выделенные из него, тоже будут удалены."
        footer={
          <>
            <Button variant="secondary" onClick={() => setDialog(false)}>
              Отмена
            </Button>
            <Button variant="danger" onClick={() => setDialog(false)}>
              Удалить резюме
            </Button>
          </>
        }
      />
    </>
  );
}
