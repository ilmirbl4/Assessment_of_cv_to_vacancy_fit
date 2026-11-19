"""Оконный инференс из конвейера fill_bd, которым подготовлена база vacancies."""

import bisect
import re
from collections import Counter
from collections.abc import Iterator, Sequence
from typing import Any, Literal, TypedDict, cast

import numpy as np
import torch
from numpy.typing import NDArray

from app.domain.models import RequirementType
from app.ml.normalization import Section

LABELS = ["O"] + [f"{prefix}-{kind.value}" for kind in RequirementType for prefix in ("B", "I")]
Range = tuple[int, int]
FloatArray = NDArray[np.float32]


class Entity(TypedDict):
    """Требование в координатах нормализованного поля вакансии."""

    requirement_type: str
    source_field: str
    span_start: int
    span_end: int
    text: str
    is_preferred: bool
    confidence: float


def require(condition: object, message: str) -> None:
    """Проверяет условия профиля импорта."""
    if not condition:
        raise ValueError(message)


PREFERENCE = r"желательно|будет плюсом|приветствуется|преимуществом будет"
MARKERS = re.compile(rf"\b(?:{PREFERENCE})\b", re.IGNORECASE)
PREFERRED_HEADER = re.compile(rf"(?:{PREFERENCE})\s*:", re.IGNORECASE)
RESET_HEADER = re.compile(
    r"(?:требования(?: к кандидату)?|обязательные требования|обязательно|условия(?: работы)?|обязанности)\s*:",
    re.IGNORECASE,
)


def preferences(text: str, sections: Sequence[Section]) -> dict[int, bool]:
    """Определяет желательность требований по заголовкам и маркерам."""
    preferred = {}
    for section in sections:
        inherited = False
        for start, end in section["items"]:
            item = text[start:end].strip()
            if PREFERRED_HEADER.fullmatch(item):
                inherited = True
            if RESET_HEADER.fullmatch(item):
                inherited = False
            positive = any(not re.search(r"\bне\s+$", item[: match.start()], re.I) for match in MARKERS.finditer(item))
            preferred[start] = inherited or positive
    return preferred


def windows(
    size: int,
    capacity: int,
    overlap: int,
    item_boundaries: Sequence[int] = (),
    word_boundaries: Sequence[int] = (),
) -> Iterator[Range]:
    """Разбивает токены на окна с учётом границ пунктов и слов."""
    require(size > 0 and 0 <= overlap < capacity, "Пустой вход модели или неверное перекрытие.")
    start = covered = 0
    while True:
        maximum = min(size, start + capacity)
        if maximum == size:
            yield start, size
            return
        # Сначала сохраняем пункт целиком. Длинный пункт режем между словами.
        end = maximum
        for boundaries in (item_boundaries, word_boundaries):
            index = bisect.bisect_right(boundaries, maximum) - 1
            if index >= 0 and boundaries[index] > covered:
                end = boundaries[index]
                break
        yield start, end
        covered = end

        target = max(start + 1, end - overlap)
        next_start = min(end, target)
        for boundaries in (item_boundaries, word_boundaries):
            index = bisect.bisect_left(boundaries, target)
            if index < len(boundaries) and start < boundaries[index] < end:
                next_start = boundaries[index]
                break
        start = next_start


def check_coverage(ranges: Sequence[Range], total: int, capacity: int) -> None:
    """Проверяет покрытие токенов окнами без пропусков."""
    covered = 0
    for start, end in ranges:
        require(
            0 <= start <= covered < end <= total and end - start <= capacity,
            "Неполное или некорректное покрытие окнами.",
        )
        covered = end
    require(covered == total, "Не обработан хвост текста.")


def check_vector(vector: FloatArray, tolerance: float = 1e-4, dim: int | None = None) -> float:
    """Проверяет размерность, dtype и единичную норму вектора."""
    require(
        vector.dtype == np.float32
        and vector.ndim == 1
        and (dim is None or vector.shape == (dim,))
        and np.isfinite(vector).all(),
        "Некорректный вектор.",
    )
    norm = float(np.linalg.norm(vector))
    require(abs(norm - 1.0) < tolerance, "Вектор не нормирован.")
    return norm


def check_entities(row: dict[str, Any], entities: Sequence[Entity]) -> None:
    """Сверяет координаты сущностей с текстом полей."""
    text = row["model_text"]
    fields = row["fields"]
    sections = {section["source_field"]: section for section in fields["source_fields"]}
    previous: dict[str, int] = {}
    for entity in sorted(entities, key=lambda x: (x["source_field"], x["span_start"])):
        field = entity["source_field"]
        require(
            field in sections and entity["requirement_type"] in {label[2:] for label in LABELS[1:]},
            "Неизвестное поле или класс сущности.",
        )
        section = sections[field]
        start, end = entity["span_start"], entity["span_end"]
        origin = section["body_start_in_model_text"]
        left, right = origin + start, origin + end
        quote = entity["text"]
        require(
            0 <= start < end <= len(fields[field])
            and start >= previous.get(field, 0)
            and fields[field][start:end] == text[left:right] == quote
            and "\n" not in quote
            and any(a <= left < right <= b for a, b in section["items"])
            and type(entity["is_preferred"]) is bool
            and 0 <= entity["confidence"] <= 1,
            "Некорректные координаты сущности.",
        )
        previous[field] = end


def decode(
    row: dict[str, Any],
    offsets: Sequence[Range],
    word_ids: Sequence[int | None],
    logits: FloatArray,
    labels: Sequence[str] = LABELS,
) -> tuple[list[Entity], dict[str, int]]:
    """Преобразует BIO-метки токенов в требования с координатами полей."""
    text = row["model_text"]
    sections = row["fields"]["source_fields"]
    items = [(start, end, section) for section in sections for start, end in section["items"]]
    left_edges = [start for start, _, _ in items]
    preferred = preferences(text, sections)
    best = logits.argmax(axis=1)
    confidence = 1 / np.exp(logits - logits.max(axis=1, keepdims=True)).sum(axis=1)
    diagnostics: Counter[str] = Counter()
    entities: list[Entity] = []
    first = last = item = None
    kind = None

    def flush() -> None:
        if first is None:
            return
        if last is None or item is None or kind is None:
            raise RuntimeError("Неполное состояние сущности при декодировании BIO-меток")
        start, end = offsets[first][0], offsets[last][1]
        if (first and word_ids[first] is not None and word_ids[first - 1] == word_ids[first]) or (
            last + 1 < len(word_ids) and word_ids[last] is not None and word_ids[last] == word_ids[last + 1]
        ):
            diagnostics["partial_word"] += 1
            return
        item_start, _, section = items[item]
        origin = section["body_start_in_model_text"]
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start == end or MARKERS.search(text[start:end]):
            diagnostics["empty_or_preference_marker"] += 1
            return
        if (
            entities
            and entities[-1]["source_field"] == section["source_field"]
            and entities[-1]["span_end"] > start - origin
        ):
            diagnostics["overlapping_offsets"] += 1
            return
        entities.append(
            Entity(
                requirement_type=kind,
                source_field=section["source_field"],
                span_start=start - origin,
                span_end=end - origin,
                text=text[start:end],
                is_preferred=preferred[item_start],
                confidence=float(confidence[first : last + 1].mean()),
            )
        )

    for i, ((start, end), label_id) in enumerate(zip(offsets, best, strict=True)):
        position = bisect.bisect_right(left_edges, start) - 1
        valid_item = position >= 0 and start < end <= items[position][1]
        label = labels[label_id]
        if label == "O" or not valid_item:
            flush()
            first = None
            if label != "O":
                diagnostics["outside_item"] += 1
            continue
        prefix, new_kind = label.split("-", 1)
        if prefix == "I" and first is not None and item == position and kind == new_kind:
            last = i
            continue
        flush()
        if prefix == "I":
            diagnostics["bio_i_as_b"] += 1
        first = last = i
        item, kind = position, new_kind
    flush()
    check_entities(row, entities)
    return entities, dict(diagnostics)


class Inference:
    """Выполняет оконный инференс моделей, использованных при импорте."""

    def __init__(
        self, stage: Literal["encoder", "ner"], path: str, threads: int, inference: dict[str, int], dim: int = 1024
    ) -> None:
        """Load a standard local export and validate its actual output contract."""
        self.stage = stage
        self.settings = inference
        self.dim = dim
        self.labels = LABELS
        torch.set_num_threads(threads)
        self.device = "cpu"
        self.batch_size = inference["batch_size"]
        self.model: Any
        self.tokenizer: Any
        if stage == "encoder":
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(path, device="cpu", local_files_only=True)
            self.tokenizer = self.model.tokenizer
            require(self.model.get_embedding_dimension() == dim, "ML_EMBEDDING_DIM не совпадает с выходом модели")
            require(inference["max_tokens"] <= self.model.max_seq_length, "Окно превышает ёмкость энкодера")
            require(not any(self.model.prompts.values()), "Экспорт с prompts пока не поддерживается")
        else:
            from transformers import AutoModelForTokenClassification, AutoTokenizer

            self.tokenizer = AutoTokenizer.from_pretrained(path, use_fast=True, local_files_only=True)
            self.model, loading = AutoModelForTokenClassification.from_pretrained(
                path, local_files_only=True, output_loading_info=True
            )
            self.labels = [self.model.config.id2label[i] for i in range(self.model.config.num_labels)]
            require(
                self.tokenizer.is_fast
                and set(self.labels) == set(LABELS)
                and not any(loading.get(key) for key in ("missing_keys", "mismatched_keys", "error_msgs")),
                "Метки, токенизатор или веса NER несовместимы",
            )
            require(inference["max_tokens"] <= self.model.config.max_position_embeddings, "Окно превышает ёмкость NER")
        self.model.eval().float()
        self.capacity = self.settings["max_tokens"] - self.tokenizer.num_special_tokens_to_add(pair=False)
        require(0 <= self.settings["overlap_tokens"] < self.capacity, "Некорректная ёмкость окна.")

    def tokenize(self, row: dict[str, Any]) -> dict[str, Any]:
        """Готовит окна токенов и сохраняет координаты исходного текста для NER."""
        # Отмеченные токенизатором специальные токены обрамляют исходную
        # последовательность. Каждый slice получает тот же template без decode.
        is_ner = self.stage == "ner"
        encoded = self.tokenizer(
            row["model_text"],
            truncation=False,
            return_special_tokens_mask=True,
            return_offsets_mapping=is_ner,
            verbose=False,
        )
        mask = encoded["special_tokens_mask"]
        start = mask.index(0)
        stop = len(mask) - mask[::-1].index(0)
        require(
            not any(mask[start:stop]) and start + len(mask) - stop == self.settings["max_tokens"] - self.capacity,
            "Неожиданный шаблон специальных токенов.",
        )
        size = stop - start
        offsets = encoded["offset_mapping"][start:stop] if is_ner else []
        word_ids = encoded.word_ids()[start:stop] if is_ner else []
        item_boundaries, word_boundaries = [], []
        if is_ner:
            starts = [left for section in row["fields"]["source_fields"] for left, _ in section["items"]]
            token_starts = [offset[0] for offset in offsets]
            item_boundaries = sorted({bisect.bisect_left(token_starts, left) for left in starts})
            word_boundaries = [i for i in range(1, size) if word_ids[i - 1] != word_ids[i]]
        ranges = list(windows(size, self.capacity, self.settings["overlap_tokens"], item_boundaries, word_boundaries))
        check_coverage(ranges, size, self.capacity)
        inputs = [
            {
                key: encoded[key][:start] + encoded[key][start + left : start + right] + encoded[key][stop:]
                for key in self.tokenizer.model_input_names
                if key in encoded
            }
            for left, right in ranges
        ]
        return dict(inputs=inputs, ranges=ranges, offsets=offsets, words=word_ids, size=size, prefix=start)

    def forward(self, inputs: list[dict[str, list[int]]]) -> FloatArray:
        """Считает векторы или logits для пакета окон."""
        batch = self.tokenizer.pad(inputs, padding=True, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            if self.stage == "encoder":
                output = torch.nn.functional.normalize(self.model(dict(batch))["sentence_embedding"], p=2, dim=1)
            else:
                output = self.model(**batch).logits
            result = output.float().cpu().numpy()
        require(np.isfinite(result).all(), f"{self.stage}: модель вернула нечисловой результат.")
        return np.asarray(result, dtype=np.float32)

    def predict(self, rows: Sequence[dict[str, Any]]) -> list[tuple[FloatArray | list[Entity], dict[str, Any]]]:
        """Обрабатывает окна пакетами и восстанавливает порядок документов."""
        documents = [self.tokenize(row) for row in rows]
        tasks = [(i, j, inputs) for i, doc in enumerate(documents) for j, inputs in enumerate(doc["inputs"])]
        tasks.sort(key=lambda task: len(task[2]["input_ids"]))
        outputs: list[list[FloatArray | None]] = [[None] * len(doc["inputs"]) for doc in documents]
        offset = 0
        while offset < len(tasks):
            batch = tasks[offset : offset + self.batch_size]
            result = self.forward([task[2] for task in batch])
            for (i, j, _), prediction in zip(batch, result, strict=True):
                outputs[i][j] = prediction
            offset += len(batch)
        predictions = []
        for row, doc, document_outputs in zip(rows, documents, outputs, strict=True):
            require(all(window is not None for window in document_outputs), "Отсутствует результат инференса окна.")
            predictions.append(self.finish(row, doc, cast(list[FloatArray], document_outputs)))
        return predictions

    def finish(
        self, row: dict[str, Any], doc: dict[str, Any], outputs: list[FloatArray]
    ) -> tuple[FloatArray | list[Entity], dict[str, Any]]:
        """Объединяет результаты окон в вектор или список требований."""
        ranges, size = doc["ranges"], doc["size"]
        meta = dict(tokens=size, ranges=ranges, capacity=self.capacity)
        if self.stage == "encoder":
            previous_end = 0
            weighted = np.zeros(self.dim, dtype=np.float32)
            for (_, end), vector in zip(ranges, outputs, strict=True):
                check_vector(vector, dim=self.dim)
                weighted += (end - previous_end) * vector
                previous_end = end
            vector = weighted / np.linalg.norm(weighted) if len(outputs) > 1 else outputs[0]
            check_vector(vector, dim=self.dim)
            return vector, meta

        context = np.full(size, -1)
        merged = np.empty((size, len(LABELS)), dtype=np.float32)
        for (start, end), window_logits in zip(ranges, outputs, strict=True):
            require(
                window_logits.ndim == 2
                and window_logits.shape[1] == len(LABELS)
                and window_logits.shape[0] >= doc["prefix"] + end - start,
                "Некорректная размерность logits.",
            )
            indices = np.arange(end - start)
            distance = np.minimum(indices, end - start - 1 - indices)
            take = distance > context[start:end]
            context[start:end][take] = distance[take]
            merged[start:end][take] = window_logits[doc["prefix"] + indices[take]]
        require((context >= 0).all(), "NER: отсутствуют предсказания.")
        entities, diagnostics = decode(row, doc["offsets"], doc["words"], merged, self.labels)
        return entities, meta | {"diagnostics": diagnostics}
