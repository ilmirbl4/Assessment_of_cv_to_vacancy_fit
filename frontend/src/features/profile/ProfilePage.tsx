import { PageTitle } from '../../components/ui/PageTitle';
import { AccountSection } from './AccountSection';
import { ResumeSection } from './ResumeSection';

/** Личный кабинет соискателя (`/profile`). */
export function ProfilePage() {
  return (
    <>
      <PageTitle title="Личный кабинет" />
      <div className="mt-6 flex max-w-200 flex-col gap-6">
        <ResumeSection />
        <AccountSection />
      </div>
    </>
  );
}
