"""Проверка сигнатур файлов и извлечение текста из PDF и DOCX (раздел 6.5 инструкции)."""

from __future__ import annotations

import io
import re
import zipfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

from app.services import errors

MAX_PDF_PAGES = 50
MAX_ZIP_ENTRIES = 1000
MAX_DOCUMENT_XML_BYTES = 20 * 1024 * 1024


def file_type_by_name(file_name: str) -> str:
    """Определяет тип по расширению (без учёта регистра).

    Raises:
        UnsupportedFormat: расширение не ``.pdf`` и не ``.docx``.
    """
    lowered = file_name.lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if lowered.endswith(".docx"):
        return "docx"
    raise errors.UnsupportedFormatError


def check_signature(file_type: str, data: bytes) -> None:
    """Проверяет, что содержимое соответствует расширению.

    Raises:
        UnsupportedFormat: сигнатура не совпала.
    """
    if file_type == "pdf":
        if b"%PDF-" not in data[:1024]:
            raise errors.UnsupportedFormatError
        return
    if not data.startswith(b"PK\x03\x04"):
        raise errors.UnsupportedFormatError
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise errors.UnsupportedFormatError
    except zipfile.BadZipFile as exc:
        raise errors.UnsupportedFormatError from exc


def clean_file_name(name: str) -> str:
    """Базовое имя файла без пути и управляющих символов, не длиннее 255 символов."""
    base = re.split(r"[/\\]", name)[-1]
    base = "".join(ch for ch in base if ch.isprintable())
    return base.strip()[:255] or "resume"


def normalize_text(text: str) -> str:
    """Схлопывает пробелы внутри строк и пустые строки, сохраняя переводы строк."""
    lines = [" ".join(line.split()) for line in text.replace("\r", "\n").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def extract_pdf(data: bytes) -> str:
    """Текст первых 50 страниц PDF.

    Raises:
        FileUnreadable: файл повреждён или защищён паролем.
    """
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise errors.FileUnreadableError
        parts = [page.extract_text() or "" for page in reader.pages[:MAX_PDF_PAGES]]
    except errors.AppError:
        raise
    except Exception as exc:
        raise errors.FileUnreadableError from exc
    return "\n".join(parts)


def extract_docx(data: bytes) -> str:
    """Текст абзацев и ячеек таблиц DOCX по порядку.

    Raises:
        FileUnreadable: файл повреждён или похож на ZIP-бомбу.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise errors.FileUnreadableError
            if archive.getinfo("word/document.xml").file_size > MAX_DOCUMENT_XML_BYTES:
                raise errors.FileUnreadableError
        document = Document(io.BytesIO(data))
        lines: list[str] = []
        for block in document.iter_inner_content():
            if isinstance(block, Paragraph):
                lines.append(block.text)
            elif isinstance(block, Table):
                for row in block.rows:
                    lines.extend(cell.text for cell in row.cells)
    except errors.AppError:
        raise
    except Exception as exc:
        raise errors.FileUnreadableError from exc
    return "\n".join(lines)
