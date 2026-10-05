from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    mongodb_uri: str
    mongodb_database: str = "sharemarket_intelligence"
    jwt_secret: str
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    cors_origins: str = "http://localhost:3000"
    allowed_hosts: str = "localhost,127.0.0.1"
    docs_enabled: bool = True
    trust_proxy_headers: bool = False

    auth_cookie_name: str = "sharem_refresh"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    auth_cookie_domain: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: int = 30
    ai_max_context_chars: int = 24000
    redis_url: str = ""
    report_font_path: str = ""
    data_scheduler_enabled: bool = True
    ingestion_timeout_seconds: int = 45
    ingestion_max_bytes: int = 50 * 1024 * 1024

    nse_eod_url_template: str = ""
    bse_eod_url_template: str = ""
    nse_index_url_template: str = ""
    bse_index_url_template: str = ""
    nse_institutional_url_template: str = ""
    nse_events_url_template: str = ""
    sector_mapping_url_template: str = ""

    live_provider_url: str = ""
    live_provider_api_key: str = ""
    live_ingest_api_key: str = ""
    live_provider_subscribe_json: str = ""
    live_max_connections: int = 100
    live_heartbeat_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [v.strip() for v in self.cors_origins.split(",") if v.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [v.strip() for v in self.allowed_hosts.split(",") if v.strip()]

    def validate_runtime(self) -> None:
        if self.access_token_minutes < 1 or self.access_token_minutes > 60:
            raise ValueError("ACCESS_TOKEN_MINUTES must be between 1 and 60")
        if self.refresh_token_days < 1 or self.refresh_token_days > 90:
            raise ValueError("REFRESH_TOKEN_DAYS must be between 1 and 90")
        if self.ai_timeout_seconds < 1 or self.ai_timeout_seconds > 120:
            raise ValueError("AI_TIMEOUT_SECONDS must be between 1 and 120")
        if self.ai_max_context_chars < 2000 or self.ai_max_context_chars > 100_000:
            raise ValueError("AI_MAX_CONTEXT_CHARS must be between 2000 and 100000")
        if self.ingestion_timeout_seconds < 5 or self.ingestion_timeout_seconds > 180:
            raise ValueError("INGESTION_TIMEOUT_SECONDS must be between 5 and 180")
        if self.ingestion_max_bytes < 1_000_000 or self.ingestion_max_bytes > 250_000_000:
            raise ValueError("INGESTION_MAX_BYTES must be between 1 MB and 250 MB")
        if self.live_max_connections < 1 or self.live_max_connections > 10_000:
            raise ValueError("LIVE_MAX_CONNECTIONS must be between 1 and 10000")
        if self.live_heartbeat_seconds < 10 or self.live_heartbeat_seconds > 300:
            raise ValueError("LIVE_HEARTBEAT_SECONDS must be between 10 and 300")
        if self.smtp_port < 1 or self.smtp_port > 65535:
            raise ValueError("SMTP_PORT must be between 1 and 65535")
        if self.auth_cookie_samesite.lower() not in {"lax", "strict", "none"}:
            raise ValueError("AUTH_COOKIE_SAMESITE must be lax, strict, or none")
        if self.app_env.lower() == "production":
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if "*" in self.cors_origin_list:
                raise ValueError("Wildcard CORS is not allowed in production")
            if not self.cors_origin_list:
                raise ValueError("CORS_ORIGINS must contain at least one origin in production")
            if not self.mongodb_uri.startswith(("mongodb://", "mongodb+srv://")):
                raise ValueError("A valid MongoDB URI is required in production")
            if not self.allowed_host_list:
                raise ValueError("ALLOWED_HOSTS must contain at least one host in production")
            if "*" in self.allowed_host_list:
                raise ValueError("Wildcard ALLOWED_HOSTS is not allowed in production")
            if not self.auth_cookie_secure:
                raise ValueError("AUTH_COOKIE_SECURE must be true in production")
            smtp_values = [self.smtp_host, self.smtp_user, self.smtp_password, self.smtp_from]
            if any(smtp_values) and not all(smtp_values):
                raise ValueError("SMTP_HOST, SMTP_USER, SMTP_PASSWORD and SMTP_FROM must be configured together")
            if not all(smtp_values):
                raise ValueError("SMTP email delivery must be configured in production because email verification is enabled")
            if self.auth_cookie_samesite.lower() == "none" and not self.auth_cookie_secure:
                raise ValueError("SameSite=None requires a Secure cookie")

settings = Settings()
settings.validate_runtime()
