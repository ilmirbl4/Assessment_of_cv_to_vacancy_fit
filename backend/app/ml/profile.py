"""Контрольные суммы артефактов и настройки инференса из fill_bd."""

import json
from pathlib import Path

PROFILE = json.loads(Path(__file__).with_name("import_profile.json").read_text(encoding="utf-8"))
