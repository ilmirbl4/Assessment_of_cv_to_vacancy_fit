import { Card } from '../../components/ui/Card';
import { Chip } from '../../components/ui/Chip';
import { useResume } from './api';

/**
 * Список навыков, выделенных из резюме.
 * @param skills навыки (пусто, пока резюме не готово)
 * @param status статус резюме
 */
export function SkillsList({ skills, status }: { skills: string[]; status: 'processing' | 'ready' | 'failed' }) {
  if (status === 'processing') return <p className="text-text-muted">Навыки появятся после обработки резюме.</p>;
  if (status === 'failed') return <p className="text-text-muted">Навыки не выделены: резюме не обработано.</p>;
  if (skills.length === 0) {
    return (
      <p className="text-text-muted">
        Не удалось выделить навыки. Проверьте, что в резюме есть раздел с навыками, и загрузите файл снова.
      </p>
    );
  }
  return (
    <>
      <p className="mb-3 text-sm text-text-muted">Выделено навыков: {skills.length}</p>
      <ul className="flex flex-wrap gap-2">
        {skills.map((skill) => (
          <li key={skill}>
            <Chip>{skill}</Chip>
          </li>
        ))}
      </ul>
    </>
  );
}

/** Секция «Навыки из резюме» личного кабинета. */
export function SkillsSection() {
  const resume = useResume();
  if (!resume.data) return null;
  return (
    <Card title="Навыки из резюме">
      <SkillsList skills={resume.data.skills} status={resume.data.status} />
    </Card>
  );
}
