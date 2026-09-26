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
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: int = 30
    report_font_path: str = ""
    data_scheduler_enabled: bool = True
    ingestion_timeout_seconds: int = 45
    nse_eod_url_template: str = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip"
    bse_eod_url_template: str = ""
    nse_index_url_template: str = ""
    bse_index_url_template: str = ""
    nse_institutional_url_template: str = ""
    nse_events_url_template: str = ""
    sector_mapping_url_template: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [v.strip() for v in self.cors_origins.split(",") if v.strip()]

settings = Settings()
