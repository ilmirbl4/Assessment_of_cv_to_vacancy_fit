import { Link } from 'react-router';
import type { Requirement } from '../../api/types';
import { Alert } from '../../components/ui/Alert';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Table, Td, Th } from '../../components/ui/Table';
import { cn } from '../../lib/cn';

/**
 * Таблица «Требования вакансии» (№, Требование, Статус) и подсказка о непокрытых требованиях.
 * @param requirements требования с признаком покрытия
 */
export function RequirementsTable({ requirements }: { requirements: Requirement[] }) {
  const hasUncovered = requirements.some((r) => r.status === 'not_covered');
  return (
    <Card title="Требования вакансии">
      <Table caption="Требования вакансии и их покрытие резюме">
        <thead>
          <tr>
            <Th className="w-14">№</Th>
            <Th>Требование</Th>
            <Th className="w-40">Статус</Th>
          </tr>
        </thead>
        <tbody>
          {requirements.map((r) => (
            <tr key={r.number} className={cn(r.status === 'not_covered' && 'bg-danger-soft/40')}>
              <Td className="tabular">{r.number}</Td>
              <Td data-user-content>{r.text}</Td>
              <Td>
                <StatusBadge kind={r.status === 'covered' ? 'covered' : 'not_covered'} />
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
      {hasUncovered ? (
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
