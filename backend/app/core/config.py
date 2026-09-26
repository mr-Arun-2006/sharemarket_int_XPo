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
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: int = 30
    redis_url: str = ""
    report_font_path: str = ""
    data_scheduler_enabled: bool = True
    ingestion_timeout_seconds: int = 45
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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [v.strip() for v in self.cors_origins.split(",") if v.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [v.strip() for v in self.allowed_hosts.split(",") if v.strip()]

    def validate_runtime(self) -> None:
        if self.app_env.lower() == "production":
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if "*" in self.cors_origin_list:
                raise ValueError("Wildcard CORS is not allowed in production")
            if not self.mongodb_uri.startswith(("mongodb://", "mongodb+srv://")):
                raise ValueError("A valid MongoDB URI is required in production")

settings = Settings()
settings.validate_runtime()
