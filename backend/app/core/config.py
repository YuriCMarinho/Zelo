import os
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5433/smartrepair"
    environment: str = "development"
    log_level: str = "INFO"
    llm_mode: str = "mock"
    llm_model: str | None = None
    llm_model_router: str = "Qwen/Qwen3.5-4B"
    llm_model_commercial: str = "Qwen/Qwen3.5-9B"
    llm_model_validator: str = "Qwen/Qwen3.5-4B"
    llm_model_resolver: str = "Qwen/Qwen3.5-9B"
    llm_model_resolver_notify: str = "Qwen/Qwen3.5-4B"
    llm_model_fallback: str = "Qwen/Qwen3.5-27B"
    recorded_demo_latency_ms: int = Field(default=80, ge=0, le=1000)
    featherless_api_key: str = "mock-key"
    langfuse_public_key: str = "mock-public"
    langfuse_secret_key: str = "mock-secret"
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_base_url: str | None = None
    max_cost_per_run_usd: float = 0.03
    max_cost_global_usd: float = 25.00
    google_places_api_key: str = ""
    provider_source: str = "web_maps"
    agent_browser_command: str = ""
    agent_browser_executable_path: str = ""
    browser_timeout_seconds: int = Field(default=35, ge=5, le=60)
    max_browser_searches: int = Field(default=50, ge=1)
    provider_contact_allowlist: str = ""
    provider_simulated_replies: str = "{}"
    provider_collection_hours: int = 12
    max_places_calls: int = 50
    # Reserva obrigatória de 30% (docs/COST.md): bloqueada até a S3/Demo Day.
    budget_reserve_usd: float = 7.50
    budget_reserve_unlocked: bool = False

    @model_validator(mode="after")
    def sync_settings(self) -> "Settings":
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
        if (self.environment == "production" or os.environ.get("RENDER")) and (
            "localhost" in self.database_url or "127.0.0.1" in self.database_url
        ):
            self.database_url = "sqlite:////tmp/smartrepair.db"
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
