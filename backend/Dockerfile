FROM python:3.12-slim
RUN useradd --create-home --uid 10001 appuser
WORKDIR /srv
COPY requirements.txt ./
RUN python -m venv /srv/.venv \
    && /srv/.venv/bin/python -m pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV PATH="/srv/.venv/bin:$PATH" PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)"
# Один воркер: лимитер входа, блокировки подбора, сборщик и планировщик живут в памяти процесса.
# Несколько воркеров потребуют вынести их из процесса (вне объёма подключения БД).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*", "--workers", "1"]
