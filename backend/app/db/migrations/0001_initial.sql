-- =====================================================================
-- Система интеллектуального подбора вакансий — схема БД (PostgreSQL 16+)
-- Требуется расширение pgvector >= 0.8 (halfvec, iterative index scan)
-- 22 таблицы
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- Упорядоченный тип: сравнение идёт по порядку объявления значений,
-- поэтому фильтр «требуемое образование не выше моего» — это education <= 'Высшее'
CREATE TYPE education_level AS ENUM (
    'Не требуется',
    'Среднее',
    'Среднее профессиональное',
    'Незаконченное высшее',
    'Высшее'
);

-- ---------------------------------------------------------------------
-- 1. Справочники
-- ---------------------------------------------------------------------

CREATE TABLE region (
    code        varchar(13)  PRIMARY KEY,          -- код региона из trudvsem
    name        text         NOT NULL
);

CREATE TABLE profession_category (
    id          integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text         NOT NULL UNIQUE      -- category.specialisation
);

-- ---------------------------------------------------------------------
-- 2. ML-модели
-- ---------------------------------------------------------------------

CREATE TABLE ml_model (
    id             integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind           text         NOT NULL CHECK (kind IN ('bi_encoder', 'cross_encoder', 'ner')),
    name           text         NOT NULL,
    version        text         NOT NULL,
    artifact_uri   text         NOT NULL,
    embedding_dim  integer      CHECK (embedding_dim BETWEEN 1 AND 4000),  -- предел HNSW для halfvec
    config         jsonb        NOT NULL DEFAULT '{}'::jsonb,
    metrics        jsonb        NOT NULL DEFAULT '{}'::jsonb,
    status         text         NOT NULL DEFAULT 'staging'
                                CHECK (status IN ('staging', 'active', 'archived')),
    created_at     timestamptz  NOT NULL DEFAULT now(),
    UNIQUE (name, version),
    UNIQUE (id, embedding_dim),                    -- цель составного FK из таблиц с эмбеддингами
    CHECK ((kind = 'bi_encoder') = (embedding_dim IS NOT NULL))
);
CREATE UNIQUE INDEX ux_ml_model_one_active ON ml_model (kind) WHERE status = 'active';

-- ---------------------------------------------------------------------
-- 3. Сбор данных
-- ---------------------------------------------------------------------

CREATE TABLE ingestion_run (
    id              uuid         PRIMARY KEY,
    mode            text         NOT NULL CHECK (mode IN ('incremental', 'full')),
    snapshot_at     timestamptz  NOT NULL,
    modified_from   timestamptz,
    complete        boolean      NOT NULL DEFAULT false,
    started_at      timestamptz  NOT NULL,
    finished_at     timestamptz,
    status          text         NOT NULL DEFAULT 'running'
                                 CHECK (status IN ('running', 'success', 'partial', 'failed')),
    pages_fetched   integer      NOT NULL DEFAULT 0,
    received        integer      NOT NULL DEFAULT 0,
    inserted        integer      NOT NULL DEFAULT 0,
    updated         integer      NOT NULL DEFAULT 0,
    unchanged       integer      NOT NULL DEFAULT 0,
    deactivated     integer      NOT NULL DEFAULT 0,
    failed          integer      NOT NULL DEFAULT 0,
    error_message   text,
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);

-- ---------------------------------------------------------------------
-- 4. Работодатели и вакансии
-- ---------------------------------------------------------------------

CREATE TABLE company (
    id           bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_code  text         NOT NULL UNIQUE,    -- company.companycode
    name         text         NOT NULL,
    inn          varchar(12),
    ogrn         varchar(15),
    kpp          varchar(9),
    site_url     text,
    updated_at   timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX ix_company_inn ON company (inn);

CREATE TABLE vacancy (
    id                   bigint           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id            text             NOT NULL UNIQUE,
    company_id           bigint           NOT NULL REFERENCES company (id),
    region_code          varchar(13)      REFERENCES region (code),
    category_id          integer          REFERENCES profession_category (id),
    employment_code      text,
    schedule_code        text,
    experience_code      text,
    education            education_level,
    title                text             NOT NULL,
    requirements         text,                              -- нормализованный текст поля requirements (вход NER)
    duties               text,                              -- нормализованный текст поля duty (вход NER)
    qualification        text,                              -- requirement.qualification, NER пока не использует
    experience_years     smallint         CHECK (experience_years >= 0),
    salary_min           integer          CHECK (salary_min > 0),
    salary_max           integer          CHECK (salary_max > 0),
    currency             char(3)          NOT NULL DEFAULT 'RUB',
    vacancy_url          text             NOT NULL,
    published_at         date             NOT NULL,
    source_modified_at   timestamptz      NOT NULL,
    first_seen_at        timestamptz      NOT NULL,
    last_seen_at         timestamptz      NOT NULL,
    updated_at           timestamptz      NOT NULL,
    is_active            boolean          NOT NULL DEFAULT true,
    closed_at            timestamptz,
    content_hash         bytea            NOT NULL,         -- sha256(title ‖ requirements ‖ duties)
    raw_payload          jsonb            NOT NULL,
    source_fields        jsonb            NOT NULL DEFAULT '[]'::jsonb,
    model_version        text             NOT NULL,
    last_ingestion_id    uuid             REFERENCES ingestion_run (id) ON DELETE SET NULL,
    CHECK (salary_max IS NULL OR salary_min IS NULL OR salary_min <= salary_max),
    CHECK (is_active OR closed_at IS NOT NULL)
);
CREATE INDEX ix_vacancy_company   ON vacancy (company_id);
CREATE INDEX ix_vacancy_filters   ON vacancy (region_code, employment_code, schedule_code, experience_code) WHERE is_active;
CREATE INDEX ix_vacancy_salary    ON vacancy (salary_max, salary_min)  WHERE is_active;
CREATE INDEX ix_vacancy_last_seen ON vacancy (last_seen_at)            WHERE is_active;

CREATE TABLE vacancy_requirement (
    id                   bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vacancy_id           bigint       NOT NULL REFERENCES vacancy (id) ON DELETE CASCADE,
    requirement_type     text         NOT NULL CHECK (requirement_type IN
                         ('HARD_SKILL', 'SOFT_SKILL', 'EXPERIENCE', 'EDUCATION', 'CERTIFICATE', 'LANGUAGE')),
    is_preferred         boolean      NOT NULL DEFAULT false,   -- «желательно», «будет плюсом» (правило после NER)
    extractor_model_id   integer      NOT NULL REFERENCES ml_model (id),
    text                 text         NOT NULL,                 -- дословный фрагмент нормализованного поля
    source_field         text         NOT NULL CHECK (source_field IN ('requirements', 'duties')),
    span_start           integer      NOT NULL CHECK (span_start >= 0),
    span_end             integer      NOT NULL,
    created_at           timestamptz  NOT NULL DEFAULT now(),
    CHECK (span_end > span_start),
    CHECK (span_end - span_start = char_length(text)),
    UNIQUE (vacancy_id, extractor_model_id, source_field, span_start, span_end)
);
CREATE INDEX ix_vreq_vacancy ON vacancy_requirement (vacancy_id, extractor_model_id);

-- Размерность не зафиксирована в типе: в одной таблице лежат векторы разных моделей.
-- Соответствие размерности модели гарантируют составной FK (model_id, dim) и CHECK.
CREATE TABLE vacancy_embedding (
    vacancy_id    bigint       NOT NULL REFERENCES vacancy (id) ON DELETE CASCADE,
    model_id      integer      NOT NULL,
    dim           integer      NOT NULL,
    embedding     halfvec      NOT NULL,             -- L2-нормирован
    content_hash  bytea        NOT NULL,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (vacancy_id, model_id),
    FOREIGN KEY (model_id, dim) REFERENCES ml_model (id, embedding_dim),
    CHECK (vector_dims(embedding) = dim)
);
-- HNSW-индекс создаётся при регистрации каждой bi_encoder-модели:
-- CREATE INDEX CONCURRENTLY ix_vemb_hnsw_m<id> ON vacancy_embedding
--     USING hnsw ((embedding::halfvec(<dim>)) halfvec_ip_ops) WITH (m = 16, ef_construction = 64)
--     WHERE model_id = <id>;

-- ---------------------------------------------------------------------
-- 5. Пользователи и резюме (только актуальное)
-- ---------------------------------------------------------------------

CREATE TABLE app_user (
    id               uuid         PRIMARY KEY,
    email            text         NOT NULL,
    password_hash    text         NOT NULL,
    role             text         NOT NULL DEFAULT 'seeker' CHECK (role IN ('seeker', 'admin')),
    is_active        boolean      NOT NULL DEFAULT true,
    filter_settings  jsonb        NOT NULL DEFAULT '{}'::jsonb,
    email_confirmed_at   timestamptz,
    consent_version      text,
    consent_accepted_at  timestamptz,
    created_at       timestamptz  NOT NULL,
    last_login_at    timestamptz,
    CHECK ((consent_version IS NULL) = (consent_accepted_at IS NULL))
);
CREATE UNIQUE INDEX ux_app_user_email ON app_user (lower(email));

CREATE TABLE user_session (
    token_hash  text         PRIMARY KEY,
    user_id     uuid         NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    created_at  timestamptz  NOT NULL,
    expires_at  timestamptz  NOT NULL
);
CREATE INDEX ix_session_user    ON user_session (user_id);
CREATE INDEX ix_session_expires ON user_session (expires_at);

CREATE TABLE auth_token (
    token_hash  text         PRIMARY KEY,
    user_id     uuid         NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    purpose     text         NOT NULL CHECK (purpose IN ('confirm_email', 'reset_password')),
    created_at  timestamptz  NOT NULL,
    expires_at  timestamptz  NOT NULL,
    used_at     timestamptz
);
CREATE INDEX ix_auth_token_user ON auth_token (user_id, purpose, created_at DESC);

CREATE TABLE resume (
    id                  uuid         PRIMARY KEY,
    user_id             uuid         NOT NULL UNIQUE REFERENCES app_user (id) ON DELETE CASCADE,
    file_name           text         NOT NULL,
    file_type           text         NOT NULL CHECK (file_type IN ('pdf', 'docx')),
    text                text         NOT NULL,
    char_count          integer      NOT NULL CHECK (char_count >= 0),
    status              text         NOT NULL CHECK (status IN ('processing', 'ready', 'failed')),
    error_message       text,
    embedding_model_id  integer,
    embedding_dim       integer,
    embedding           halfvec,
    model_version       text,
    uploaded_at         timestamptz  NOT NULL,
    processed_at        timestamptz,
    FOREIGN KEY (embedding_model_id, embedding_dim) REFERENCES ml_model (id, embedding_dim),
    CHECK ((embedding IS NULL) = (embedding_model_id IS NULL)),
    CHECK ((embedding IS NULL) = (embedding_dim IS NULL)),
    CHECK (embedding IS NULL OR vector_dims(embedding) = embedding_dim),
    CHECK (status <> 'ready' OR embedding IS NOT NULL)
);
CREATE INDEX ix_resume_emb_model ON resume (embedding_model_id);
CREATE INDEX ix_resume_processing ON resume (uploaded_at) WHERE status = 'processing';

CREATE TABLE resume_fragment (
    id           bigint   GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resume_id    uuid     NOT NULL REFERENCES resume (id) ON DELETE CASCADE,
    ord          integer  NOT NULL CHECK (ord >= 0),
    text         text     NOT NULL,
    span_start   integer  NOT NULL CHECK (span_start >= 0),
    span_end     integer  NOT NULL,
    CHECK (span_end > span_start),
    UNIQUE (resume_id, ord)
);

-- ---------------------------------------------------------------------
-- 6. Подбор: оценки покрытия, текущая выдача, избранное
-- ---------------------------------------------------------------------

CREATE TABLE requirement_coverage (
    resume_id         uuid         NOT NULL REFERENCES resume (id) ON DELETE CASCADE,
    requirement_id    bigint       NOT NULL REFERENCES vacancy_requirement (id) ON DELETE CASCADE,
    model_id          integer      NOT NULL REFERENCES ml_model (id),
    status            text         NOT NULL
                                   CHECK (status IN ('covered', 'partial', 'not_covered')),
    score             real         NOT NULL CHECK (score BETWEEN 0 AND 1),
    best_fragment_id  bigint       REFERENCES resume_fragment (id) ON DELETE CASCADE,  -- цитата
    computed_at       timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (resume_id, requirement_id, model_id),
    CHECK ((status = 'not_covered') = (best_fragment_id IS NULL))
);
CREATE INDEX ix_cov_requirement ON requirement_coverage (requirement_id);
CREATE INDEX ix_cov_fragment    ON requirement_coverage (best_fragment_id) WHERE best_fragment_id IS NOT NULL;

CREATE TABLE recommendation_set (
    user_id           uuid         PRIMARY KEY REFERENCES app_user (id) ON DELETE CASCADE,
    run_id            uuid         NOT NULL UNIQUE,
    resume_id         uuid         NOT NULL REFERENCES resume (id) ON DELETE CASCADE,
    bi_encoder_id     integer      NOT NULL REFERENCES ml_model (id),
    cross_encoder_id  integer      NOT NULL REFERENCES ml_model (id),
    filters           jsonb        NOT NULL DEFAULT '{}'::jsonb,
    candidates_k      integer      NOT NULL CHECK (candidates_k > 0),
    top_n             integer      NOT NULL CHECK (top_n > 0),
    computed_at       timestamptz  NOT NULL DEFAULT now(),
    CHECK (top_n <= candidates_k)
);
CREATE INDEX ix_recset_resume ON recommendation_set (resume_id);

CREATE TABLE recommendation_item (
    user_id          uuid      NOT NULL REFERENCES recommendation_set (user_id) ON DELETE CASCADE,
    rank             integer   NOT NULL CHECK (rank >= 1),
    vacancy_id       bigint    NOT NULL REFERENCES vacancy (id) ON DELETE CASCADE,
    retrieval_score  real      NOT NULL,
    coverage_score   real      NOT NULL CHECK (coverage_score BETWEEN 0 AND 1),
    final_score      real      NOT NULL,
    match_percent    smallint  NOT NULL CHECK (match_percent BETWEEN 0 AND 100),
    PRIMARY KEY (user_id, rank),
    UNIQUE (user_id, vacancy_id)
);
CREATE INDEX ix_item_vacancy ON recommendation_item (vacancy_id);

CREATE TABLE favorite (
    user_id     uuid         NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    vacancy_id  bigint       NOT NULL REFERENCES vacancy (id) ON DELETE CASCADE,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, vacancy_id)
);
CREATE INDEX ix_favorite_vacancy ON favorite (vacancy_id);

-- ---------------------------------------------------------------------
-- 7. Мониторинг: агрегаты и обезличенная статистика
-- ---------------------------------------------------------------------

CREATE TABLE quality_daily_stat (
    day               date     NOT NULL,
    bi_encoder_id     integer  NOT NULL REFERENCES ml_model (id),
    cross_encoder_id  integer  NOT NULL REFERENCES ml_model (id),
    rank              integer  NOT NULL CHECK (rank >= 1),
    impressions       integer  NOT NULL DEFAULT 0 CHECK (impressions >= 0),
    favorites         integer  NOT NULL DEFAULT 0 CHECK (favorites >= 0),
    clicks            integer  NOT NULL DEFAULT 0 CHECK (clicks >= 0),
    PRIMARY KEY (day, bi_encoder_id, cross_encoder_id, rank)
);

CREATE TABLE resume_stat (
    id              bigint     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_id        integer    NOT NULL REFERENCES ml_model (id),
    uploaded_on     date       NOT NULL,
    char_count      integer    NOT NULL CHECK (char_count >= 0),
    fragment_count  integer    NOT NULL CHECK (fragment_count >= 0),
    emb_projection  real[]     NOT NULL CHECK (cardinality(emb_projection) BETWEEN 1 AND 64)
);
CREATE INDEX ix_resume_stat_day ON resume_stat (model_id, uploaded_on);

-- Одна строка = одна метрика одной проверки; проверку идентифицирует (entity_type, checked_at)
CREATE TABLE drift_metric (
    id              bigint            GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type     text              NOT NULL CHECK (entity_type IN ('vacancy', 'resume')),
    checked_at      timestamptz       NOT NULL,
    model_id        integer           REFERENCES ml_model (id),
    reference_from  timestamptz       NOT NULL,
    reference_to    timestamptz       NOT NULL,
    current_from    timestamptz       NOT NULL,
    current_to      timestamptz       NOT NULL,
    reference_uri   text,
    metric          text              NOT NULL CHECK (metric IN ('psi', 'ks', 'adversarial_auc')),
    feature         text              NOT NULL,
    value           double precision  NOT NULL,
    p_value         double precision,
    threshold       double precision  NOT NULL,
    is_alert        boolean           NOT NULL,
    CHECK (reference_from < reference_to AND current_from < current_to),
    UNIQUE (entity_type, checked_at, metric, feature)
);
CREATE INDEX ix_drift_time ON drift_metric (entity_type, checked_at DESC);

-- Обезличенные события для дашбордов; связи с пользователем нет намеренно
CREATE TABLE matching_event (
    run_id         uuid         PRIMARY KEY,
    at             timestamptz  NOT NULL,
    duration_ms    integer      NOT NULL CHECK (duration_ms >= 0),
    results_count  integer      NOT NULL CHECK (results_count >= 0)
);
CREATE INDEX ix_matching_event_at ON matching_event (at);

CREATE TABLE favorite_from_run_event (
    run_id  uuid         PRIMARY KEY,
    at      timestamptz  NOT NULL
);
CREATE INDEX ix_favorite_event_at ON favorite_from_run_event (at);
