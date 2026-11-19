#!/bin/sh
set -eu
# Run from repository root. No credentials, training state or database files are included.
python3 backend/scripts/download_models.py --verify
mkdir -p data/artifacts
tar --exclude='*/.cache' -czf data/artifacts/runtime-artifacts.tar.gz models/manifest.json models/USER-bge-m3 models/rubert-mini-frida-ner models/mmarco-mMiniLMv2-L12-H384-v1 data/reference
tar -czf data/artifacts/private-ner.tar.gz models/rubert-mini-frida-ner
sha256sum data/artifacts/*.tar.gz > data/artifacts/SHA256SUMS
