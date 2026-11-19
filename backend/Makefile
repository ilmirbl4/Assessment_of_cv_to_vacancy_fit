PYTHON ?= python3
VENV_PYTHON = .venv/bin/python

.PHONY: install models run lint typecheck verify
install:
	$(PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install -r requirements-dev.txt
models:
	$(VENV_PYTHON) -m scripts.download_models --verify
run:
	$(VENV_PYTHON) -m uvicorn app.main:app --port 8000 --workers 1
lint:
	$(VENV_PYTHON) -m ruff check app scripts
	$(VENV_PYTHON) -m ruff format --check app scripts
typecheck:
	$(VENV_PYTHON) -m mypy app
verify: lint typecheck
