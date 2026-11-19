"""Fetch only pinned public runtime files; private NER must be supplied as an archive."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Verify local files without network")
    parser.add_argument(
        "--refresh-manifest", action="store_true", help="Explicitly register an intentionally replaced export"
    )
    args = parser.parse_args()
    manifest_path = ROOT / "models/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for name, entry in manifest["models"].items():
        folder = ROOT / "models" / name
        if args.refresh_manifest:
            from app.ml.artifacts import artifact_files

            entry["files"] = artifact_files(str(folder))
            entry["origin"] = "operator supplied export"
            entry["revision"] = None
            continue
        revision = entry.get("revision")
        origin = entry["origin"]
        for relative, sha in entry["files"].items():
            path = folder / relative
            if not path.is_file() and not args.verify and revision:
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_suffix(path.suffix + ".partial")
                url = f"https://huggingface.co/{origin}/resolve/{revision}/{relative}"
                with urlopen(url, timeout=120) as response, temp.open("wb") as stream:
                    while block := response.read(1024 * 1024):
                        stream.write(block)
                if digest(temp) != sha:
                    raise SystemExit("Checksum mismatch: " + relative)
                temp.replace(path)
            if not path.is_file():
                raise SystemExit(
                    f"Missing {path}. Supply the private/exported artifact bundle described in models/README.md"
                )
            if digest(path) != sha:
                raise SystemExit("Checksum mismatch: " + str(path))
        print("Verified", name)
    if args.refresh_manifest:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        print("Manifest updated; commit it with the model release metadata")


if __name__ == "__main__":
    main()
