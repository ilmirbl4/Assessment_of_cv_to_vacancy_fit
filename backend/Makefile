.PHONY: install models run lint typecheck db-migrate

install:
	uv sync

models:
	uv run --extra ml python scripts/download_models.py

run:
	uv run uvicorn app.main:app --reload --port 8000

lint:
	uv run ruff check . && uv run ruff format --check .

typecheck:
	uv run mypy app

db-migrate:
	uv run python -m app.db.migrate

# Тесты, нагрузочные и сквозные проверки вынесены в ../../cv_vacancy_fit_dev_tools
