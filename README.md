# Assessment_of_cv_to_vacancy_fit

Курсовая работа по ТРПС: система интеллектуального анализа соответствия резюме требованиям
вакансии. Сервер — FastAPI, клиент — React/Vite, хранение — PostgreSQL 16 + pgvector.
Система поставляется одним репозиторием и запускается из корня одной командой Compose.
Нейросетевые артефакты лежат в `models/`, эталон вакансий — в `data/reference/`; соседние
проекты, хостовой Python и кэш Hugging Face для штатного запуска не нужны.

## Состав

| Каталог | Назначение |
|---|---|
| `backend/` | FastAPI, модели, импорт, мониторинг, миграции, тесты |
| `frontend/` | React-клиент, nginx и проксирование `/api` |
| `models/` | локальные веса трёх моделей и `manifest.json` |
| `data/reference/` | неизменяемый эталон 20 000 вакансий и manifest |
| `data/demo/` | демонстрационные JSON, резюме и ручной набор пар кросс-энкодера |
| `ml/`, `collector/`, `monitoring/`, `deploy/` | настройки подсистем, Compose-overlays, backup/restore |
| `docs/` | ТЗ, руководство запуска, отчёт реализации, ограничения моделей |

## Быстрый старт (локально, управляемая БД)

Нужны Docker Engine с Compose v2 и ~8 ГБ RAM. Модели и эталон должны быть доставлены
(см. `models/README.md`).

```bash
python3 backend/scripts/configure.py     # создаёт отсутствующие .env из *.example, не перезаписывает существующие
# Укажите SMTP_* и, при необходимости, ADMIN_* в backend/.env.
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8080/api/v1/status
```

Клиент: `http://127.0.0.1:8080`. Backend и PostgreSQL наружу не публикуются.
`/api/v1/status` показывает фазу подготовки, прогресс и ошибку; `/api/v1/health` — liveness.
Первичная загрузка демонстрационного JSON, подготовка моделей, миграции и эталон выполняются
автоматически. Повторный `docker compose up` не переимпортирует готовый корпус.

### Три сценария

Сценарий выбирается файлами в корневом `.env` (переменная `COMPOSE_FILE`):

```dotenv
# 1. Локально, управляемая контейнерная БД
COMPOSE_FILE=docker-compose.yml:deploy/compose.db.yml:deploy/compose.local.yml

# 2. Локально, существующий PostgreSQL по TCP
COMPOSE_FILE=docker-compose.yml:deploy/compose.local.yml
# deploy/db.env: DB_MODE=external, POSTGRES_HOST=host.docker.internal (Linux: host-gateway),
# POSTGRES_PORT, POSTGRES_DB/USER/PASSWORD

# 3. Сервер: управляемая БД, HTTPS и backup
COMPOSE_FILE=docker-compose.yml:deploy/compose.db.yml:deploy/compose.server.yml
# DOMAIN и ACME_EMAIL в корневом .env, APP_ENV=production в backend/.env
```

Несовместимые сочетания отвергаются валидатором `backend/app/config.py`. Внешняя БД при
`DB_MODE=external` не подменяется пустой локальной при ошибке пароля или адреса.

## Настройки

Владение файлами не дублируется: пароль БД и пороги заданы в одном месте.

| Файл | Содержимое |
|---|---|
| `.env` | `COMPOSE_PROJECT_NAME`, `COMPOSE_FILE`, `APP_ENV`, `PUBLIC_BASE_URL`, порты, образы, `MODELS_DIR`, `DATA_DIR`, `DOMAIN`, `ACME_EMAIL` |
| `deploy/db.env` | `DB_MODE`, реквизиты PostgreSQL, пул, миграции, HNSW |
| `deploy/backup.env` | время, retention, каталог и часовой пояс backup |
| `backend/.env` | SMTP, сессии/cookies, администратор, лимиты, таймауты резюме |
| `ml/.env` | пути/размерности/окна/batch моделей, пороги покрытия |
| `collector/.env` | API/JSON источник, расписание, batch, retry |
| `monitoring/.env` | эталон, минимумы выборок, PSI/AUC/KS, окно отклика |

`.env` и `*.env` с секретами игнорируются Git; шаблоны `*.env.example` — нет. В production
обязательны пароль БД, `COOKIE_SECURE=true`, HTTPS `PUBLIC_BASE_URL`, API-сбор не реже
24 часов и уникальный `ADMIN_PASSWORD` длиной не менее 12 символов.

## Модели и эталон

- `USER-bge-m3` — 1024 измерения, CLS pooling, L2, окна до 8192 токенов.
- `rubert-mini-frida-ner` — BIO шести типов, окна 512/128, координаты в нормализованном поле.
- `mmarco-mMiniLMv2-L12-H384-v1` — кросс-энкодер, сырой логит и один sigmoid в приложении.
- Эталон — 20 000 вакансий запуска `8b001c18-dd71-4128-bf37-82e8f009f08e`,
  `reference_id=trudvsem-20000-66d729a0f8051cbb`, снимок `2026-10-19T19:26:44Z`.

Скачивание публичных файлов, проверка hashes, упаковка приватной NER и ограничения качества
описаны в [models/README.md](models/README.md). При старте модели загружаются офлайн, hashes
сверяются, несовместимая размерность останавливает запуск с понятной ошибкой.

## Демонстрация

1. `data/demo/initial.json` — первоначальный импорт 30 вакансий (реальный формат источника).
2. Положите `data/demo/incremental-shift.json` в `data/input/incremental/` и нажмите
   «Запустить сбор» в `/admin/collection` (или дождитесь таймера). Второй файл проходит те же
   модели; повторная загрузка того же checksum не создаёт дублей.
3. Дрейф: `/admin/drift` за период, `/admin/drift/data|model|feedback`. Сдвиг демонстрационных
   данных виден при достаточных выборках; при 30 вакансиях разделы честно показывают
   `insufficient_data`/`reference_missing`, а не выдуманные нули.
4. Зарегистрируйте пользователя, подтвердите почту, загрузите PDF/DOCX до 5 МБ и запустите
   подбор. В карточке — требования, цитата и один из трёх статусов.

Полный сценарий и типовые ошибки — в [docs/integration/README.md](docs/integration/README.md).

## Администрирование

`/admin/collection`, `/admin/speed`, `/admin/drift` доступны только роли `admin`; соискатель
получает 403 и на прямые запросы `/api/v1/admin/*`. Администратор создаётся идемпотентно из
`ADMIN_EMAIL`/`ADMIN_PASSWORD` и не пересоздаётся при рестарте. Явная смена пароля:
`cd backend && .venv/bin/python -m scripts.set_password --email <адрес>`; команда закрывает сессии.

## Резервные копии

```bash
# разовый backup в том, смонтированный в /backups сервисом backup
docker compose exec backup /opt/backup/backup.sh once
# восстановление ТОЛЬКО в новую БД (не поверх рабочей)
docker compose exec backup /opt/backup/restore.sh /backups/<файл>.dump cvfit_restore
```

Сервис `backup` в серверном overlay делает ежедневный `pg_dump` в custom-формате, проверяет
читаемость, публикует файл атомарно и хранит 7 успешных копий (настраивается). Restore
создаёт явно названную новую БД, проверяет архив и печатает количество вакансий и пользователей.
Копии содержат персональные данные и не публикуются веб-сервером.

## Проверки

```bash
cd backend
make install     # создаёт .venv, устанавливает зависимости через pip
make verify      # стиль, форматирование и типы

cd ../frontend
npm ci
npm run typecheck && npm run lint && npm run build
```

Для ручной установки из `backend/` в активном окружении используйте `python -m pip install -r requirements.txt`
(или `requirements-dev.txt` для разработки). PyTorch устанавливается в CPU-сборке.

CI проверяет стиль и типы backend и frontend, а также собирает клиент.

## Известные ограничения

- Кросс-энкодер `mmarco-mMiniLMv2` обучен релевантности, а не трём статусам выполнения
  требований. Предварительная калибровка (15 ручных пар) показывает пересечение классов;
  пороги 0.45/0.75 не откалиброваны. См. [docs/models/calibration.md](docs/models/calibration.md).
- Резюме не прогоняется через NER: для подбора нужны только фрагменты и embedding.
  NER остаётся частью обработки вакансий, где извлекаются требования.
- Эталон содержит только вакансии. Отдельные эталоны резюме, оценок и отклика не выдумываются:
  без подключённых артефактов соответствующие разделы показывают причину отсутствия данных.
- Публичный HTTPS требует реального домена, DNS и открытых портов 80/443; локально проверены
  конфигурация Compose/Caddy и cookie/forwarded-заголовки, но не выпуск сертификата.

## Документация

- [docs/integration/README.md](docs/integration/README.md) — запуск, сценарии, ошибки, поставка.
- [docs/integration/IMPLEMENTATION_REPORT.md](docs/integration/IMPLEMENTATION_REPORT.md) — фактические
  результаты, измерения и внешние препятствия.
- [docs/integration/REPOSITORY_CLEANUP_INSTRUCTION.md](docs/integration/REPOSITORY_CLEANUP_INSTRUCTION.md) —
  исходное задание (выполнено).
- [docs/ТЗ_Система_подбора_вакансий.pdf](docs/ТЗ_Система_подбора_вакансий.pdf) — техническое задание.
