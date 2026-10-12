import { NavLink, useNavigate } from 'react-router';
import { Briefcase } from 'lucide-react';
import { Link } from 'react-router';
import { homePath, useLogout, useMe } from '../../features/auth/api';
import { cn } from '../../lib/cn';
import { Button } from '../ui/Button';

const seekerNav = [
  { to: '/', label: 'Подбор вакансий', end: true },
  { to: '/favorites', label: 'Избранное', end: false },
  { to: '/profile', label: 'Личный кабинет', end: false },
];
const adminNav = [{ to: '/admin/collection', label: 'Администрирование', end: false, match: '/admin' }];

/**
 * Шапка сайта: логотип, меню по роли, email и «Выйти». Гостю показывает только логотип.
 */
export function AppHeader() {
  const me = useMe().data;
  const logout = useLogout();
  const navigate = useNavigate();
  const nav = me?.role === 'admin' ? adminNav : me ? seekerNav : [];

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-surface">
      <div className="mx-auto flex h-16 w-full max-w-page items-center gap-8 px-6">
        <Link to={me ? homePath(me.role) : '/login'} className="flex items-center gap-2 text-lg font-semibold">
          <Briefcase aria-hidden="true" size={24} strokeWidth={2} className="text-primary" />
          Подбор вакансий
        </Link>
        {nav.length > 0 ? (
          <nav aria-label="Основное меню" className="flex h-full flex-1 gap-6">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'inline-flex h-full items-center border-b-2 text-base font-medium',
                    isActive ? 'border-primary text-primary' : 'border-transparent text-text-muted hover:text-text',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        ) : (
          <div className="flex-1" />
        )}
        {me ? (
          <div className="flex items-center gap-4">
            <span data-user-content title={me.email} className="max-w-55 truncate text-sm text-text-muted">
              {me.email}
            </span>
            <Button
              variant="ghost"
              size="sm"
              loading={logout.isPending}
              onClick={() => logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) })}
            >
              Выйти
            </Button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
