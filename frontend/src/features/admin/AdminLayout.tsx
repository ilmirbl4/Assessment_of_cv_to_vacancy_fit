import { Outlet, useSearchParams } from 'react-router';
import { PageTitle } from '../../components/ui/PageTitle';
import { Tabs } from '../../components/ui/Tabs';
import { hasDriftWarning, useDrift } from './api';

/** Макет админки: заголовок, вкладки-маршруты и индикатор предупреждения на вкладке «Дрейф данных». */
export function AdminLayout() {
  const [params] = useSearchParams();
  const drift = useDrift(params.get('from') ?? undefined, params.get('to') ?? undefined);
  const warning = drift.data ? hasDriftWarning(drift.data) : false;
  return (
    <>
      <PageTitle title="Администрирование" documentTitle="Администрирование" />
      <div className="mt-4">
        <Tabs
          label="Разделы администрирования"
          items={[
            { to: '/admin/collection', label: 'Сбор данных' },
            { to: '/admin/speed', label: 'Скорость подбора' },
            { to: '/admin/drift', label: 'Дрейф данных', warning },
          ]}
        />
      </div>
      <div className="mt-6">
        <Outlet />
      </div>
    </>
  );
}
