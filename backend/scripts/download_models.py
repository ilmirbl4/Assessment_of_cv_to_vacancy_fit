"""Скачивает модель cointegrated/rubert-tiny2 в ../models/rubert-tiny2 (запуск: ``make models``)."""

from huggingface_hub import snapshot_download

snapshot_download("cointegrated/rubert-tiny2", local_dir="../models/rubert-tiny2")
