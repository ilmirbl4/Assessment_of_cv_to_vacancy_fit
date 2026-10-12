import { Outlet } from 'react-router';
import { Briefcase } from 'lucide-react';

/** Макет страниц входа: логотип и карточка 420px по центру. */
export function AuthLayout() {
  return (
    <main className="flex min-h-screen flex-col items-center px-6 pt-[10vh] pb-12">
      <div className="mb-6 flex items-center gap-2 text-lg font-semibold">
        <Briefcase aria-hidden="true" size={24} strokeWidth={2} className="text-primary" />
        Подбор вакансий
      </div>
      <div className="w-full max-w-105 rounded-lg border border-border bg-surface p-8 shadow-card">
        <Outlet />
      </div>
    </main>
  );
}
