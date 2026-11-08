from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5433/smartrepair"
    environment: str = "development"
    log_level: str = "INFO"
    llm_mode: str = "mock"
    featherless_api_key: str = "mock-key"
    langfuse_public_key: str = "mock-public"
    langfuse_secret_key: str = "mock-secret"
    langfuse_host: str = "https://cloud.langfuse.com"
    max_cost_per_run_usd: float = 0.03
    max_cost_global_usd: float = 25.00
    google_places_api_key: str = ""
    provider_source: str = "fixture"
    provider_contact_allowlist: str = ""
    provider_simulated_replies: str = "{}"
    provider_collection_hours: int = 12
    max_places_calls: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
