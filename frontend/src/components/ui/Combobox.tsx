import { useState } from 'react';
import { Combobox as HeadlessCombobox, ComboboxInput, ComboboxOption, ComboboxOptions } from '@headlessui/react';
import { Check, ChevronDown } from 'lucide-react';
import type { Option } from '../../api/types';
import { cn } from '../../lib/cn';
import { controlClasses } from './Input';

interface ComboboxProps {
  id?: string;
  options: Option[];
  /** Код выбранного пункта; пустая строка — пункт «Все…». */
  value: string;
  onChange: (code: string) => void;
  /** Текст первого пункта, например «Все регионы». */
  allLabel: string;
  'aria-describedby'?: string;
  'aria-invalid'?: true;
}

/** Выделяет совпадение с запросом полужирным начертанием. */
function highlight(text: string, query: string) {
  const index = query ? text.toLowerCase().indexOf(query.toLowerCase()) : -1;
  if (index < 0) return text;
  return (
    <>
      {text.slice(0, index)}
      <span className="font-semibold">{text.slice(index, index + query.length)}</span>
      {text.slice(index + query.length)}
    </>
  );
}

/**
 * Выпадающий список с поиском на базе Headless UI Combobox.
 * @param props варианты, значение, обработчик и подпись пункта «Все…»
 */
export function Combobox({ id, options, value, onChange, allLabel, ...aria }: ComboboxProps) {
  const [query, setQuery] = useState('');
  const all: Option = { code: '', name: allLabel };
  const list = [all, ...options];
  const filtered = query ? list.filter((o) => o.code !== '' && o.name.toLowerCase().includes(query.toLowerCase())) : list;
  const selected = list.find((o) => o.code === value) ?? all;

  return (
    <HeadlessCombobox
      value={selected}
      onChange={(option: Option | null) => onChange(option?.code ?? '')}
      onClose={() => setQuery('')}
      by="code"
    >
      <div className="relative">
        <ComboboxInput
          id={id}
          data-user-content
          className={cn(controlClasses, 'pr-9')}
          displayValue={(option: Option | null) => option?.name ?? ''}
          onChange={(e) => setQuery(e.target.value)}
          {...aria}
        />
        <ChevronDown aria-hidden="true" size={16} strokeWidth={2} className="pointer-events-none absolute right-3 top-3 text-text-muted" />
        <ComboboxOptions
          anchor="bottom"
          className="z-40 mt-1 max-h-72 w-(--input-width) overflow-auto rounded-md border border-border bg-surface py-1 shadow-raised empty:invisible"
        >
          {filtered.length === 0 ? (
            <div className="px-3 py-2 text-text-muted">Ничего не найдено</div>
          ) : (
            filtered.map((option) => (
              <ComboboxOption
                key={option.code || 'all'}
                value={option}
                data-user-content={option.code ? '' : undefined}
                className="flex cursor-pointer items-center justify-between gap-2 px-3 py-2 text-base data-focus:bg-primary-soft"
              >
                <span>{highlight(option.name, query)}</span>
                {option.code === value ? <Check aria-hidden="true" size={16} strokeWidth={2} className="text-primary" /> : null}
              </ComboboxOption>
            ))
          )}
        </ComboboxOptions>
      </div>
    </HeadlessCombobox>
  );
}
