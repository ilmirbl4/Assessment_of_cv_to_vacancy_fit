-- Durable pipeline activation, staging and idempotent observation history.
CREATE TABLE pipeline_state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    pipeline_id text,
    phase text NOT NULL DEFAULT 'pending',
    progress bigint NOT NULL DEFAULT 0,
    total bigint NOT NULL DEFAULT 0,
    error text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    initial_complete boolean NOT NULL DEFAULT false,
    next_collection_at timestamptz NOT NULL DEFAULT now(),
    next_full_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO pipeline_state(singleton) VALUES(true);
CREATE TABLE processing_job (
    id text PRIMARY KEY,
    kind text NOT NULL,
    status text NOT NULL DEFAULT 'running' CHECK(status IN ('running','success','failed')),
    cursor bigint NOT NULL DEFAULT 0,
    total bigint NOT NULL DEFAULT 0,
    metadata jsonb NOT NULL DEFAULT '{}',
    error text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE vacancy_analysis (
    vacancy_id bigint NOT NULL REFERENCES vacancy(id) ON DELETE CASCADE,
    pipeline_id text NOT NULL,
    content_hash bytea NOT NULL,
    ner_id integer NOT NULL REFERENCES ml_model(id),
    bi_id integer NOT NULL REFERENCES ml_model(id),
    PRIMARY KEY(vacancy_id,pipeline_id)
);
CREATE TABLE staged_vacancy (
    job_id text NOT NULL REFERENCES processing_job(id) ON DELETE CASCADE,
    vacancy_id bigint NOT NULL REFERENCES vacancy(id) ON DELETE CASCADE,
    content_hash bytea NOT NULL,
    analysis jsonb NOT NULL,
    PRIMARY KEY(job_id,vacancy_id)
);
CREATE TABLE resume_analysis (
    resume_id uuid NOT NULL REFERENCES resume(id) ON DELETE CASCADE,
    pipeline_id text NOT NULL,
    model_id integer NOT NULL,
    dim integer NOT NULL,
    embedding halfvec NOT NULL,
    fragments jsonb NOT NULL,
    skills jsonb NOT NULL,
    normalized_text text NOT NULL,
    PRIMARY KEY(resume_id,pipeline_id),
    FOREIGN KEY(model_id,dim) REFERENCES ml_model(id,embedding_dim),
    CHECK(vector_dims(embedding)=dim)
);
CREATE TABLE match_cache (
    resume_id uuid NOT NULL REFERENCES resume(id) ON DELETE CASCADE,
    vacancy_id bigint NOT NULL REFERENCES vacancy(id) ON DELETE CASCADE,
    pipeline_id text NOT NULL,
    content_hash bytea NOT NULL,
    result jsonb NOT NULL,
    PRIMARY KEY(resume_id,vacancy_id,pipeline_id)
);
CREATE TABLE source_batch (
    checksum text PRIMARY KEY,
    file_name text NOT NULL,
    run_id uuid NOT NULL REFERENCES ingestion_run(id),
    cursor bigint NOT NULL DEFAULT 0,
    complete boolean NOT NULL DEFAULT false
);
CREATE TABLE feature_observation (
    event_key text PRIMARY KEY,
    source_id text NOT NULL,
    content_hash text NOT NULL,
    pipeline_id text NOT NULL,
    reference_id text NOT NULL,
    batch_id uuid REFERENCES ingestion_run(id) ON DELETE SET NULL,
    observed_at timestamptz NOT NULL DEFAULT now(),
    features jsonb NOT NULL
);
CREATE INDEX ix_features_period ON feature_observation(pipeline_id,observed_at);
CREATE TABLE reference_features (
    reference_id text NOT NULL,
    pipeline_id text NOT NULL,
    source_id text NOT NULL,
    content_hash text NOT NULL,
    features jsonb NOT NULL,
    PRIMARY KEY(reference_id,pipeline_id,source_id)
);
CREATE TABLE monitoring_cache (
    cache_key text PRIMARY KEY,
    computed_at timestamptz NOT NULL DEFAULT now(),
    payload jsonb NOT NULL
);
CREATE TABLE resume_observation (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observed_at timestamptz NOT NULL DEFAULT now(),
    pipeline_id text NOT NULL,
    features jsonb NOT NULL
);
ALTER TABLE matching_event ADD COLUMN pipeline_id text;
CREATE TABLE score_observation (
    run_id uuid PRIMARY KEY REFERENCES matching_event(run_id) ON DELETE CASCADE,
    pipeline_id text NOT NULL,
    score real NOT NULL CHECK(score BETWEEN 0 AND 1)
);
CREATE TABLE requirement_embedding (
    text_hash text NOT NULL,
    model_id integer NOT NULL,
    dim integer NOT NULL,
    embedding halfvec NOT NULL,
    PRIMARY KEY(text_hash,model_id),
    FOREIGN KEY(model_id,dim) REFERENCES ml_model(id,embedding_dim),
    CHECK(vector_dims(embedding)=dim)
);
