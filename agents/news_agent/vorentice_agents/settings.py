"""Application settings — single source of truth, loaded from environment.

Every tunable lives here so operators can reconfigure the agent without
touching code. Secrets never appear in source; they arrive via `.env`
locally and Azure Key Vault (injected env vars) in production.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI connection settings."""

    model_config = SettingsConfigDict(
        env_prefix="AZURE_OPENAI_", env_file=(".env", ".env.local"), extra="ignore"
    )

    endpoint: str = ""
    api_key: str = ""
    api_version: str = "2024-10-21"
    deployment: str = "gpt-4o-mini"

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key)


class NewsAgentSettings(BaseSettings):
    """Behavioural knobs for the News Agent pipeline."""

    model_config = SettingsConfigDict(
        env_prefix="NEWS_", env_file=(".env", ".env.local"), extra="ignore"
    )

    max_llm_articles: int = Field(default=60, ge=1, le=500)
    run_interval_minutes: int = Field(default=30, ge=5)
    dry_run: bool = False
    # Minimum heuristic score (0-1) an article needs to reach the LLM.
    prefilter_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    # LLM classification batch size — articles per completion call.
    llm_batch_size: int = Field(default=8, ge=1, le=20)
    # How far back GDELT queries look on each run.
    gdelt_timespan: str = "1h"
    # Daily Brief window — the digest covers items from the last N hours.
    digest_window_hours: int = Field(default=24, ge=1, le=168)
    http_timeout_seconds: float = 20.0
    # Hard per-source SLA — a slow/throttled provider is cut off here.
    source_fetch_budget_seconds: float = 45.0


class ExternalSourcesSettings(BaseSettings):
    """API keys for external data sources. Field names map to the exact
    env var names (case-insensitive). A blank value keeps that source
    dormant — the registry omits it and the pipeline never errors on it."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"), extra="ignore"
    )

    eia_api_key: str = ""
    fred_api_key: str = ""
    opensanctions_api_key: str = ""
    acled_api_key: str = ""
    acled_email: str = ""
    noaa_cdo_token: str = ""
    # Default placeholder is NOT an approved ReliefWeb appname; the
    # registry treats this exact value as "not configured".
    reliefweb_appname: str = "vorentice-news-agent"


class AppSettings(BaseSettings):
    """Top-level settings aggregate."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"), extra="ignore"
    )

    database_url: str = "sqlite:///./vorentice_news.db"

    azure_openai: AzureOpenAISettings = Field(default_factory=AzureOpenAISettings)
    news: NewsAgentSettings = Field(default_factory=NewsAgentSettings)
    sources: ExternalSourcesSettings = Field(
        default_factory=ExternalSourcesSettings
    )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Cached settings accessor — import this, not AppSettings()."""
    return AppSettings()
