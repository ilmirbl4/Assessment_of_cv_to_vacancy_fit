"""Validated, bounded JSON/JSONL source; only atomically published files are read."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


def checksum(path: Path) -> str:
    """SHA-256 of a reference or input file."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def records(path: Path, max_bytes: int) -> Any:
    """JSON arrays are size bounded; JSONL is streamed, including gzip archives."""
    opener = gzip.open if path.suffix == ".gz" else open
    if path.name.endswith((".jsonl", ".jsonl.gz")):
        with opener(path, "rt", encoding="utf8") as stream:
            for line in stream:
                if len(line.encode()) > max_bytes:
                    raise ValueError("Слишком большая строка JSONL")
                if line.strip():
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError("JSONL должен содержать объекты")
                    yield row.get("vacancy", row)
        return
    if path.stat().st_size > max_bytes:
        raise ValueError("JSON превышает JSON_MAX_BYTES; используйте JSONL")
    with path.open(encoding="utf8") as stream:
        document = json.load(stream)
    if not isinstance(document, dict):
        raise ValueError("Ожидается объект с vacancies")
    rows = document.get("vacancies", document.get("results", {}).get("vacancies"))
    if not isinstance(rows, list):
        raise ValueError("Отсутствует массив vacancies")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Вакансия должна быть объектом")
        yield row.get("vacancy", row)
    for source_id in document.get("closed_ids", []):
        if not isinstance(source_id, str):
            raise ValueError("closed_ids должен содержать строки")
        yield {"_closed_id": source_id}


def inspect(path: Path, max_bytes: int) -> tuple[str, int]:
    """Validate the entire file before committing its first batch."""
    before = checksum(path)
    count = sum(1 for _ in records(path, max_bytes))
    if checksum(path) != before:
        raise ValueError("Файл изменился при чтении; публикуйте атомарным rename")
    return before, count
