import { SearchX } from 'lucide-react';
import { ButtonLink } from '../components/ui/ButtonLink';
import { EmptyState } from '../components/ui/EmptyState';
import { useDocumentTitle } from '../components/ui/PageTitle';
import { homePath, useMe } from '../features/auth/api';

/** Страница 404. */
export function NotFoundPage() {
  const me = useMe().data;
  useDocumentTitle('Страница не найдена');
  return (
    <EmptyState
      icon={SearchX}
      title="Страница не найдена"
      headingLevel={1}
      action={<ButtonLink to={me ? homePath(me.role) : '/login'}>На главную</ButtonLink>}
    />
  );
}
