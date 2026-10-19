import { Link } from 'react-router';
import type { Requirement } from '../../api/types';
import { Alert } from '../../components/ui/Alert';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Table, Td, Th } from '../../components/ui/Table';
import { cn } from '../../lib/cn';

const rowTint: Record<Requirement['status'], string | false> = {
  covered: false,
  partially_covered: 'bg-warning-soft/40',
  not_covered: 'bg-danger-soft/40',
};

/**
 * Таблица «Требования вакансии» (№, Требование, Цитата из резюме, Статус) и подсказка о непокрытых требованиях.
 * Цитата — фраза резюме, которой кросс-энкодер покрывает требование.
 * @param requirements требования с вердиктом и цитатой
 */
export function RequirementsTable({ requirements }: { requirements: Requirement[] }) {
  const hasGaps = requirements.some((r) => r.status !== 'covered');
  return (
    <Card title="Требования вакансии">
      <Table caption="Требования вакансии и их покрытие резюме">
        <thead>
          <tr>
            <Th className="w-14">№</Th>
            <Th>Требование</Th>
            <Th>Цитата из резюме</Th>
            <Th className="w-52">Статус</Th>
          </tr>
        </thead>
        <tbody>
          {requirements.map((r) => (
            <tr key={r.number} className={cn(rowTint[r.status])}>
              <Td className="tabular">{r.number}</Td>
              <Td data-user-content>{r.text}</Td>
              <Td>
                {r.resume_quote ? (
                  <q data-user-content className="line-clamp-3 text-text-muted" title={r.resume_quote}>
                    {r.resume_quote}
                  </q>
                ) : (
                  <span className="text-text-muted">
                    <span aria-hidden="true">—</span>
                    <span className="sr-only">Подходящей фразы в резюме нет</span>
                  </span>
                )}
              </Td>
              <Td>
                <StatusBadge kind={r.status} />
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
      {hasGaps ? (
        <Alert variant="info" className="mt-4">
          Если вы обладаете навыками из непокрытых требований, добавьте их в резюме — это повысит степень
          соответствия.{' '}
          <Link to="/profile" className="font-medium text-primary underline underline-offset-2">
            Перейти в личный кабинет
          </Link>
        </Alert>
      ) : null}
    </Card>
  );
}
