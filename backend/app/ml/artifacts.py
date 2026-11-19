"""Content-based model identity and offline artifact integrity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.ml.profile import PROFILE


def fingerprint(value: Any) -> str:
    """Stable semantic identity, independent of location and dictionary order."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def artifact_files(path: str) -> dict[str, str]:
    """Hash runtime files; exclude docs, caches and training checkpoints."""
    root = Path(path)
    if not (root / "config.json").is_file() or not list(root.glob("*.safetensors")):
        raise ValueError(f"Нет экспорта модели в {root}: нужны config.json и *.safetensors. См. models/README.md")
    result = {}
    for file in sorted(root.rglob("*")):
        relative = file.relative_to(root)
        if (
            file.is_file()
            and not any(part.startswith((".", "checkpoint")) for part in relative.parts)
            and file.suffix in {".json", ".safetensors", ".txt", ".model"}
        ):
            with file.open("rb") as stream:
                result[relative.as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def identity(stage: str, path: str, inference: dict[str, int], manifest_path: str) -> tuple[str, dict[str, Any]]:
    """Verify delivery manifest and retain legacy IDs only for the proven contract."""
    files = artifact_files(path)
    manifest = Path(manifest_path)
    if not manifest.is_file():
        raise ValueError("Отсутствует models/manifest.json; подготовьте проверенный пакет артефактов")
    entries = json.loads(manifest.read_text())["models"].values()
    if not any(all(entry["files"].get(k) == v for k, v in files.items()) for entry in entries):
        raise ValueError(f"Контрольные суммы модели {path} не совпадают с manifest.json")
    semantic = {k: v for k, v in inference.items() if k != "batch_size"}
    config = {"files": files, "inference": semantic, "normalization": PROFILE["processing"], "contract": "windows-v1"}
    old = PROFILE["profiles"].get(stage)
    if old and all(files.get(k) == v for k, v in old["config"]["files"].items()):
        old_semantic = {k: v for k, v in old["config"]["inference"].items() if k != "batch_size"}
        if semantic == old_semantic:
            return old["version"], config
    return fingerprint(config), config
