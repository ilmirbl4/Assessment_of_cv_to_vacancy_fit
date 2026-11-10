"""Настройки приложения (переменные окружения, раздел 11 инструкции)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_RESULTS = 100
PAGE_SIZE = 10
MAX_PAGE = 10
MAX_JSON_BODY_BYTES = 64 * 1024


class Settings(BaseSettings):
    """Настройки сервера; значения читаются из окружения и ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    storage_backend: str = "memory"
    database_url: str = ""
    db_pool_min: int = Field(default=2, ge=1)
    db_pool_max: int = Field(default=15, ge=1)
    db_auto_migrate: bool = True
    db_hnsw_ef_search: int = Field(default=300, ge=1, le=1000)
    seed_demo_data: bool = False
    seed_vacancies_dir: str = ""
    seed_vacancies_limit: int = 20_000
    seed_synthetic_vacancies: int = 0
    seed_perf_users: int = 0
    admin_email: str = ""
    admin_password: str = ""
    email_backend: str = "console"
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_security: str = "ssl"
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
    ml_cross_encoder_path: str = ""
    ml_model_version: str = ""
    ml_bi_encoder_path: str = ""
    ml_bi_encoder_version: str = ""
    ml_bi_encoder_max_seq_length: int = 512
    ml_torch_threads: int = 2
    ml_batch_size: int = 64
    trudvsem_base_url: str = "https://opendata.trudvsem.ru/api/v1"
    collector_enabled: bool = False
    collector_incremental_interval_min: int = 360
    collector_full_run_time: str = "03:00"
    collector_workers: int = Field(default=4, ge=1, le=4)
    collector_industries: str = ""
    collector_min_coverage: float = 0.98

    @property
    def trusted_origin_list(self) -> list[str]:
        """Список доверенных origin."""
        return [o.strip() for o in self.trusted_origins.split(",") if o.strip()]

    @property
    def collector_industry_list(self) -> list[str]:
        """Коды сфер для ограничения сбора."""
        return [o.strip() for o in self.collector_industries.split(",") if o.strip()]
