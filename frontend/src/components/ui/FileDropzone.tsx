import { type DragEvent, useRef, useState } from 'react';
import { Upload } from 'lucide-react';
import { cn } from '../../lib/cn';
import { Button } from './Button';

interface FileDropzoneProps {
  onFile: (file: File) => void;
  loading?: boolean;
}

/**
 * Зона загрузки резюме: перетаскивание и кнопка «Загрузить резюме».
 * @param onFile вызывается с выбранным файлом (проверка формата — на стороне родителя)
 * @param loading показать спиннер на кнопке
 */
export function FileDropzone({ onFile, loading = false }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file && !loading) onFile(file);
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={cn(
        'flex flex-col items-center gap-3 rounded-lg border-2 border-dashed p-8 text-center',
        dragging ? 'border-primary bg-primary-soft' : 'border-border-strong',
      )}
    >
      <Upload aria-hidden="true" size={32} strokeWidth={1.5} className="text-text-muted" />
      <div className="flex flex-wrap items-center justify-center gap-3">
        <span>Перетащите файл сюда или</span>
        <Button loading={loading} onClick={() => inputRef.current?.click()}>
          Загрузить резюме
        </Button>
      </div>
      <p className="text-sm text-text-muted">DOCX или PDF с текстовым слоем, не более 5 МБ</p>
      <input
        ref={inputRef}
        type="file"
        accept=".docx,.pdf"
        className="hidden"
        data-testid="resume-input"
        aria-label="Файл резюме"
        tabIndex={-1}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = '';
          if (file) onFile(file);
        }}
      />
    </div>
  );
}
