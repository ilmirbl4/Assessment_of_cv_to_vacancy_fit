"""Настройки приложения (переменные окружения, раздел 11 инструкции)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_RESULTS = 100
PAGE_SIZE = 10
MAX_PAGE = 10
MAX_JSON_BODY_BYTES = 64 * 1024


class Settings(BaseSettings):
    """Настройки сервера; значения читаются из окружения и ``.env``."""

    model_config = SettingsConfigDict(
        env_file=tuple(
            str(Path(__file__).resolve().parents[1] / name)
            for name in ("../deploy/db.env", "../ml/.env", "../collector/.env", "../monitoring/.env", ".env")
        ),
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: str = "dev"
    app_timezone: str = "Europe/Moscow"
    log_level: str = "INFO"
    docs_enabled: bool = True
    public_base_url: str = "http://localhost:5173"
    trusted_origins: str = ""
    session_cookie_name: str = "session"
    session_ttl_hours: int = 168
    cookie_secure: bool = True
    confirm_token_ttl_hours: int = 24
    reset_token_ttl_minutes: int = 60
    login_max_failures: int = 10
    storage_backend: Literal["postgres"] = "postgres"
    db_mode: Literal["managed", "external"] = "managed"
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "vacancies"
    postgres_user: str = "vacancies"
    postgres_password: str = ""
    db_connect_attempts: int = Field(default=10, ge=1)
    db_connect_retry_s: float = Field(default=2, gt=0)
    db_pool_min: int = Field(default=2, ge=1)
    db_pool_max: int = Field(default=15, ge=1)
    db_auto_migrate: bool = True
    db_hnsw_ef_search: int = Field(default=300, ge=1, le=1000)
    admin_email: str = ""
    admin_password: str = ""
    email_backend: Literal["smtp"] = "smtp"
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_security: Literal["ssl", "starttls"] = "ssl"
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_from_name: str = "Подбор вакансий"
    smtp_timeout_s: int = 10
    resume_min_text_chars: int = 100
    resume_processing_timeout_s: float = 25
    match_rerank_top_n: int = 300
    match_phrases_per_requirement: int = 5
    ml_covered_threshold: float = 0.75
    ml_partial_threshold: float = 0.45
    ml_cross_encoder_path: str = "/models/mmarco-mMiniLMv2-L12-H384-v1"
    ml_bi_encoder_path: str = "/models/USER-bge-m3"
    ml_ner_path: str = "/models/rubert-mini-frida-ner"
    ml_torch_threads: int = 2
    ml_batch_size: int = 64
    trudvsem_base_url: str = "https://opendata.trudvsem.ru/api/v1"
    collector_enabled: bool = True
    collector_incremental_interval_min: int = 360
    collector_full_run_time: str = "03:00"
    collector_workers: int = Field(default=4, ge=1, le=4)
    collector_industries: str = ""
    collector_min_coverage: float = 0.98

    ml_embedding_dim: int = Field(default=1024, ge=1, le=4000)
    ml_encoder_max_tokens: int = Field(default=8192, ge=8)
    ml_encoder_overlap: int = Field(default=64, ge=0)
    ml_encoder_batch_size: int = Field(default=2, ge=1)
    ml_ner_max_tokens: int = Field(default=512, ge=8)
    ml_ner_overlap: int = Field(default=128, ge=0)
    ml_ner_batch_size: int = Field(default=8, ge=1)
    ml_max_pending: int = Field(default=12, ge=1)
    ml_manifest_path: str = "/models/manifest.json"
    collector_source: Literal["api", "json"] = "json"
    initial_vacancies_path: str = "/data/demo/initial.json"
    incremental_vacancies_dir: str = "/data/input/incremental"
    collector_batch_size: int = Field(default=32, ge=1, le=256)
    collector_retry_s: int = Field(default=300, ge=1)
    collector_overlap_min: int = Field(default=10, ge=0)
    collector_max_attempts: int = Field(default=5, ge=1)
    collector_tick_s: float = Field(default=10, gt=0)
    json_max_bytes: int = Field(default=256 * 1024 * 1024, ge=1)
    monitoring_reference_path: str = "/data/reference"
    monitoring_min_samples: int = Field(default=100, ge=10)
    monitoring_bins: int = Field(default=10, ge=2)
    monitoring_psi_threshold: float = Field(default=0.2, gt=0)
    monitoring_auc_threshold: float = Field(default=0.6, ge=0, le=1)
    monitoring_ks_alpha: float = Field(default=0.05, gt=0, lt=1)
    monitoring_favorite_max_drop: float = Field(default=0.05, ge=0, le=1)
    monitoring_favorite_window_hours: int = Field(default=24, ge=1)
    monitoring_resume_reference: str = ""
    monitoring_score_reference: str = ""
    monitoring_favorite_reference: str = ""
    monitoring_seed: int = 42

    @property
    def database_url(self) -> str:
        """DSN из единственного набора реквизитов, с URL-кодированием."""
        auth = quote(self.postgres_user, safe="") + ":" + quote(self.postgres_password, safe="")
        if self.postgres_host.startswith("/"):
            return f"postgresql://{auth}@/{quote(self.postgres_db, safe='')}?host={quote(self.postgres_host)}"
        return f"postgresql://{auth}@{self.postgres_host}:{self.postgres_port}/{quote(self.postgres_db, safe='')}"

    @model_validator(mode="after")
    def validate_contract(self) -> Settings:
        """Отвергает несовместимые настройки до подключения к БД."""
        if not 0 <= self.ml_partial_threshold < self.ml_covered_threshold <= 1:
            raise ValueError("Нужно 0 <= ML_PARTIAL_THRESHOLD < ML_COVERED_THRESHOLD <= 1")
        if self.db_pool_max < self.db_pool_min:
            raise ValueError("DB_POOL_MAX меньше DB_POOL_MIN")
        if self.db_mode == "managed" and self.postgres_host != "db":
            raise ValueError("DB_MODE=managed требует POSTGRES_HOST=db")
        if self.collector_incremental_interval_min <= 0:
            raise ValueError("Интервал сбора должен быть положительным")
        if self.app_env == "production":
            if not self.postgres_password or not self.cookie_secure or not self.public_base_url.startswith("https://"):
                raise ValueError("Production требует пароль БД, COOKIE_SECURE=true и HTTPS PUBLIC_BASE_URL")
            if self.collector_source != "api" or self.collector_incremental_interval_min > 1440:
                raise ValueError("Production требует API-сбор с интервалом не более 24 часов")
            if (
                not self.admin_email
                or len(self.admin_password) < 12
                or self.admin_password in {"Admin1234", "Password1"}
            ):
                raise ValueError("Задайте ADMIN_EMAIL и уникальный ADMIN_PASSWORD (не менее 12 символов)")
        return self

    @property
    def trusted_origin_list(self) -> list[str]:
        """Список доверенных origin."""
        return [o.strip() for o in self.trusted_origins.split(",") if o.strip()]

    @property
    def collector_industry_list(self) -> list[str]:
        """Коды сфер для ограничения сбора."""
        return [o.strip() for o in self.collector_industries.split(",") if o.strip()]
