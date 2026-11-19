"""Совместимая предобработка из ner_text.py, homoglyphs.py и exp_utils.py."""

import html
import re
import unicodedata
from typing import TypedDict

# Латинские буквы, внешне неотличимые от кириллических
_LAT2CYR = str.maketrans(
    {
        "A": "А",
        "B": "В",
        "C": "С",
        "E": "Е",
        "H": "Н",
        "K": "К",
        "M": "М",
        "O": "О",
        "P": "Р",
        "T": "Т",
        "X": "Х",
        "Y": "У",
        "a": "а",
        "c": "с",
        "e": "е",
        "o": "о",
        "p": "р",
        "x": "х",
        "y": "у",
        "k": "к",
        "m": "м",
        "t": "т",
        "h": "н",
    }
)
_LOOKALIKE = {chr(k) for k in _LAT2CYR}  # ключи maketrans — коды символов
_LETTERS = re.compile(r"[A-Za-zА-Яа-яЁё]+")  # цифры, дефисы, пробелы разделяют слова
_CYR = re.compile(r"[А-Яа-яЁё]")
_INVISIBLE = re.compile("[\u200b-\u200f\u2060\ufeff\u00ad]")  # нулевая ширина, мягкий перенос


def _fix_token(m: re.Match[str]) -> str:
    w = m.group(0)
    if not _CYR.search(w):  # чисто латинские слова (Office, PHP, Fix) не трогаем
        return w
    latin = [ch for ch in w if ch.isascii()]
    if not latin or any(ch not in _LOOKALIKE for ch in latin):
        return w  # латиница без кириллического двойника: не угадываем
    return w.translate(_LAT2CYR)


def normalize_text(s: str) -> str:
    """Очищает невидимые символы и заменяет латинские двойники в смешанных словах."""
    if not isinstance(s, str):
        return s
    s = _INVISIBLE.sub("", s).replace("\xa0", " ")
    return _LETTERS.sub(_fix_token, s)


# ---------------------------------------------------------------- B. пустышки
# Значения (после нормализации: нижний регистр, ё->е, обрезка пробелов и концевой пунктуации),
# которые означают «ничего не сказано». Составлено по 200 частотным значениям qualification и
# requirements. Профессии («врач»), уровни образования, разряды и «опыт работы» пустышками НЕ считаются.
PLACEHOLDERS = {
    "",
    "нет",
    "не требуется",
    "не требуются",
    "требуется",
    "да",
    "без требований",
    "нет требований",
    "требований нет",
    "требования не предъявляются",
    "требования не предъявляется",
    "не предъявляются",
    "не предъявляется",
    "без предъявления требований",
    "без предъявления требований к квалификации",
    "без требований к квалификации",
    "требования к квалификации не предъявляются",
    "квалификация не требуется",
    "не требует квалификации",
    "не требующие квалификации",
    "без квалификации",
    "не указано",
    "не указана",
    "не указан",
    "не имеет значения",
    "не обязательно",
    "необязательно",
    "любая",
    "любое",
    "отсутствует",
    "отсутствуют",
    "без особых требований",
    "дополнительных требований нет",
    "без опыта",
    "без опыта работы",
    "можно без опыта",
    "можно без опыта работы",
    "опыт не требуется",
    "опыт работы не требуется",
    "без подготовки",
    "соответствует",
    "соответствие занимаемой должности",
    "согласно должностной инструкции",
    "в соответствии с должностной инструкцией",
    "в соответствии с заявленной вакансией",
    "при собеседовании",
    "по результатам собеседования",
    "по собеседованию",
    "без категории",
    "нет опыта",
    "не важно",
    "неважно",
}
_PH_RE = re.compile(r"^[\W\d_]*$")  # только цифры/пунктуация: «-», «.», «1», «0», «--»


def norm_value(s: str) -> str:
    """Приводит строку к формату сравнения со списком заполнителей."""
    s = (s or "").lower().replace("ё", "е").strip()
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,;:!-–—\"'«»()")


def is_placeholder(s: str) -> bool:
    """Проверяет, содержит ли поле только заполнители."""
    n = norm_value(s)
    return n in PLACEHOLDERS or bool(_PH_RE.match(n))


_TAG = re.compile(r"<[^<>]{1,200}>")
_SPACES = re.compile(r"[ \t\r\f\v]+")
_BULLET = re.compile(r"[•●▪◦■►✓✔·]")
# дефис/тире — граница пункта только в начале поля или после «;» / «.» (дефис внутри слова не делит)
_DASH = re.compile(r"(?:^|(?<=[;.]))\s*[-–—]+\s*(?=[^\s\-–—])")
# «1.» / «1)» в начале, после пробела или «;:,»; не часть десятичного числа и не шифр «А.1.»
_NUM = re.compile(r"(?:^|(?<=[\s;:,]))(\d{1,2})\s?[.)](?!\d)\s*")
_EDGE = " \t.;,"
SEP = "\x00"


def clean(s: object) -> str:
    """Шаги 2–3: невидимые символы, двойники, HTML, пробелы."""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFC", html.unescape(s))  # «и» + бреве -> «й», «е» + диерезис -> «ё»
    s = _TAG.sub(" ", s)
    s = normalize_text(s)  # невидимые символы, nbsp, кириллические двойники
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _SPACES.sub(" ", s)
    return s.strip()


def split_items(s: str) -> list[str]:
    """Шаг 5: пункты списка. Поле без маркеров — один пункт."""
    if not s:
        return []
    s = s.replace("\n", SEP)
    s = _BULLET.sub(SEP, s)
    nums = [int(x) for x in _NUM.findall(s)]
    if len(set(nums)) >= 2 and (1 in nums or 2 in nums):
        s = _NUM.sub(SEP, s)
    s = SEP.join(_DASH.sub(SEP, part) for part in s.split(SEP))
    items = []
    for part in s.split(SEP):
        part = part.strip().rstrip(_EDGE).lstrip(" \t;,.").strip()
        if part:
            items.append(part)
    return items


VERSION = "ner-text-2026-11-12-v1"


class Section(TypedDict):
    """Координаты секции и её пунктов во входном тексте модели."""

    source_field: str
    raw_path: str
    normalization_version: str
    body_start_in_model_text: int
    body_end_in_model_text: int
    items: list[list[int]]


def prepare_text(requirements: object, duty: object) -> tuple[str, dict[str, str], list[Section]]:
    """Собирает вход модели, тексты секций и координаты пунктов."""
    bodies = {"requirements": "", "duties": ""}
    sections: list[Section] = []
    text = ""
    for field, raw_path, header, raw in (
        ("requirements", "requirements", "Требования:", requirements),
        ("duties", "duty", "Обязанности:", duty),
    ):
        cleaned = clean(raw)
        items = [] if is_placeholder(cleaned) else split_items(cleaned)
        if not items:
            continue
        if text:
            text += "\n\n"
        text += header + "\n"
        start = len(text)
        intervals: list[list[int]] = []
        for item in items:
            if intervals:
                text += "\n"
            text += "- "
            intervals.append([len(text), len(text) + len(item)])
            text += item
        bodies[field] = text[start:]
        sections.append(
            {
                "source_field": field,
                "raw_path": raw_path,
                "normalization_version": VERSION,
                "body_start_in_model_text": start,
                "body_end_in_model_text": len(text),
                "items": intervals,
            }
        )
    return text, bodies, sections
