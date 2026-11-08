from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5433/smartrepair"
    environment: str = "development"
    log_level: str = "INFO"
    llm_mode: str = "mock"
    recorded_demo_latency_ms: int = Field(default=80, ge=0, le=1000)
    featherless_api_key: str = "mock-key"
    langfuse_public_key: str = "mock-public"
    langfuse_secret_key: str = "mock-secret"
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_base_url: str | None = None
    max_cost_per_run_usd: float = 0.03
    max_cost_global_usd: float = 25.00
    google_places_api_key: str = ""
    provider_source: str = "fixture"
    provider_contact_allowlist: str = ""
    provider_simulated_replies: str = "{}"
    provider_collection_hours: int = 12
    max_places_calls: int = 50
    # Reserva obrigatória de 30% (docs/COST.md): bloqueada até a S3/Demo Day.
    budget_reserve_usd: float = 7.50
    budget_reserve_unlocked: bool = False

    @model_validator(mode="after")
    def sync_settings(self) -> "Settings":
        if self.llm_mode.lower() == "real":
            self.llm_mode = "featherless"
        if self.langfuse_base_url and (
            self.langfuse_host == "https://cloud.langfuse.com" or not self.langfuse_host
        ):
            self.langfuse_host = self.langfuse_base_url
        return self

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
