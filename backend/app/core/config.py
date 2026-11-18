from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://pulsesearch:pulsesearch@localhost:5432/pulsesearch"
    db_pool_size: int = 10
    db_max_overflow: int = 5

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 20
    allowed_extensions: str = ".pdf,.txt,.md"

    embedding_provider: str = "local"  # "local" | "hosted"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    embedding_api_base_url: str = ""
    embedding_api_key: str = ""
    embedding_api_model: str = ""

    cors_origins: str = "http://localhost:3000"

    search_cache_ttl_seconds: int = 60
    hybrid_keyword_weight: float = 0.6
    hybrid_semantic_weight: float = 0.4

    rerank_enabled: bool = True
    rerank_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # Each candidate costs one cross-encoder forward pass; benchmarking (see
    # docs/performance.md) showed 25 roughly doubling p95/p99 search latency
    # under concurrent load versus 10, for no meaningfully better ordering at
    # the result-set sizes this app actually returns.
    rerank_candidate_pool: int = 10
    # Cross-encoder relevance floor: a candidate scoring below this is treated
    # as "not actually relevant" and dropped rather than shown as a low-ranked
    # match. Without this, retrieval always returns its top-K regardless of
    # whether anything is truly relevant — cosine similarity is virtually
    # never exactly zero, so a query with no real matches (a stopword, a typo,
    # a term absent from the corpus) still "finds" documents. Measured on real
    # queries: genuinely relevant results scored +3 to +6, irrelevant ones
    # scored -9 to -11 — a wide, consistent gap, so 0.0 is a safe cut line
    # rather than a finely-tuned one.
    rerank_min_score: float = 0.0

    rate_limit_enabled: bool = True
    rate_limit_search_per_minute: int = 30
    rate_limit_upload_per_minute: int = 10

    storage_backend: str = "local"  # "local" | "s3"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint_url: str = ""  # set for MinIO/S3-compatible backends
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    database_url_replica: str = ""  # optional read replica; falls back to database_url

    worker_metrics_port: int = 9100

    seed_demo_documents: bool = True

    # AI Q&A: ask a question in plain English, get a synthesized answer with
    # citations instead of a list of snippets. Off by default — needs a real
    # Anthropic API key, and unlike every other feature in this app, each
    # request has a real per-call cost.
    ai_answers_enabled: bool = False
    anthropic_api_key: str = ""
    ai_answers_model: str = "claude-opus-5"
    ai_answers_max_tokens: int = 1024
    ai_answers_effort: str = "medium"  # low | medium | high | xhigh | max
    # How many of the top search results become the model's grounding context.
    # Reuses the same hybrid-search + reranking + relevance-floor pipeline as
    # /api/search — including the fact that a query with no relevant matches
    # returns zero chunks, so the model is never even called for it (see
    # QAService.ask): no context in means no hallucinated answer out.
    ai_answers_context_chunks: int = 5
    ai_answers_cache_ttl_seconds: int = 300

    rate_limit_ask_per_minute: int = 10

    # Email: password reset (and future transactional email) goes through
    # this. Unset SMTP_HOST means emails are logged instead of sent (see
    # app/services/email/console_provider.py) — the flow works end-to-end in
    # local dev without real mail credentials, so there's no real-provider
    # gate blocking development the way AI answers has.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@pulsesearch.local"
    smtp_use_tls: bool = True

    # Base URL of the deployed frontend, used to build links inside emails
    # (e.g. the password reset link) — the API has no other way to know
    # where the frontend is actually hosted.
    frontend_base_url: str = "http://localhost:3000"

    password_reset_token_ttl_minutes: int = 30
    rate_limit_password_reset_per_minute: int = 5

    job_max_retries: int = 3

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",") if ext.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
