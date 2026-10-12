import { Controller, type UseFormReturn } from 'react-hook-form';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Checkbox } from '../../components/ui/Checkbox';
import { Combobox } from '../../components/ui/Combobox';
import { Field } from '../../components/ui/Field';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import type { Dictionaries, Option } from '../../api/types';
import type { FiltersFormValues } from '../../lib/validation';

function Options({ items }: { items: Option[] }) {
  return (
    <>
      <option value="">Любой</option>
      {items.map((o) => (
        <option key={o.code} value={o.code} data-user-content>
          {o.name}
        </option>
      ))}
    </>
  );
}

interface FiltersPanelProps {
  form: UseFormReturn<FiltersFormValues>;
  dictionaries: Dictionaries | undefined;
  loading: boolean;
  onSubmit: (values: FiltersFormValues) => void;
  onReset: () => void;
}

/**
 * Панель фильтров подбора: регион, зарплата, занятость, график, опыт; кнопки «Подобрать вакансии» и «Сбросить фильтры».
 */
export function FiltersPanel({ form, dictionaries, loading, onSubmit, onReset }: FiltersPanelProps) {
  const { register, control, handleSubmit, formState } = form;
  return (
    <Card title="Фильтры" className="sticky top-22 w-80 shrink-0 self-start">
      <form noValidate onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <fieldset className="flex flex-col gap-4">
          <legend className="sr-only">Параметры подбора</legend>
          <Field label="Регион">
            {(p) => (
              <Controller
                control={control}
                name="region_code"
                render={({ field }) => (
                  <Combobox
                    options={dictionaries?.regions ?? []}
                    value={field.value}
                    onChange={field.onChange}
                    allLabel="Все регионы"
                    {...p}
                  />
                )}
              />
            )}
          </Field>
          <Field label="Минимальная зарплата, ₽" error={formState.errors.min_salary?.message}>
            {(p) => <Input inputMode="numeric" suffix="₽" autoComplete="off" {...p} {...register('min_salary')} />}
          </Field>
          <Checkbox label="Только с указанной зарплатой" {...register('only_with_salary')} />
          <Field label="Тип занятости">
            {(p) => (
              <Select {...p} {...register('employment_type')}>
                <Options items={dictionaries?.employment_types ?? []} />
              </Select>
            )}
          </Field>
          <Field label="График работы">
            {(p) => (
              <Select {...p} {...register('schedule')}>
                <Options items={dictionaries?.schedules ?? []} />
              </Select>
            )}
          </Field>
          <Field label="Требуемый опыт работы">
            {(p) => (
              <Select {...p} {...register('experience')}>
                <Options items={dictionaries?.experience ?? []} />
              </Select>
            )}
          </Field>
        </fieldset>
        <Button type="submit" fullWidth loading={loading} disabled={!dictionaries}>
          Подобрать вакансии
        </Button>
        <button type="button" onClick={onReset} className="self-start text-sm text-primary hover:underline">
          Сбросить фильтры
        </button>
      </form>
    </Card>
  );
}
