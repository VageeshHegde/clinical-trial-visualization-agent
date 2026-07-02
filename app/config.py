from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1", validation_alias="OPENAI_MODEL")

    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")
    cors_origins: str = Field(default="*", validation_alias="CORS_ORIGINS")

    clinical_trials_base_url: str = Field(
        default="https://clinicaltrials.gov/api/v2",
        validation_alias="CLINICAL_TRIALS_BASE_URL",
    )
    clinical_trials_timeout: float = Field(default=30.0, validation_alias="CLINICAL_TRIALS_TIMEOUT")
    clinical_trials_max_page_size: int = Field(
        default=200,
        validation_alias="CLINICAL_TRIALS_MAX_PAGE_SIZE",
    )
    clinical_trials_user_agent: str = Field(
        default="clinical-trial-visualization-agent/0.1",
        validation_alias="CLINICAL_TRIALS_USER_AGENT",
    )
    aggregation_top_n: int = Field(
        default=25,
        validation_alias="AGGREGATION_TOP_N",
        description="Max buckets returned to the agent for large breakdowns (sponsor, condition)",
    )

    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @field_validator("clinical_trials_max_page_size")
    @classmethod
    def validate_page_size(cls, value: int) -> int:
        return min(max(value, 1), 1000)

    @field_validator("aggregation_top_n")
    @classmethod
    def validate_aggregation_top_n(cls, value: int) -> int:
        return min(max(value, 5), 100)

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    def require_openai_api_key(self) -> str:
        if not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and add your API key."
            )
        return self.openai_api_key

    def apply(self) -> None:
        """Expose settings to libraries that read from the process environment."""
        api_key = self.openai_api_key
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_DEFAULT_MODEL"] = self.openai_model


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Clear cached settings (e.g. after .env change) and reload."""
    get_settings.cache_clear()
    return get_settings()
