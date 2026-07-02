from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_VENV_REEXEC_ENV = "CLINICAL_TRIALS_AGENT_VENV_REEXEC"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", validation_alias="OPENAI_MODEL")

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
        description="Upper bound for ClinicalTrials.gov API pageSize on internal fetches",
    )
    clinical_trials_scan_page_size: int = Field(
        default=1000,
        validation_alias="CLINICAL_TRIALS_SCAN_PAGE_SIZE",
        description="Page size when scanning studies for sponsor/condition aggregation",
    )
    clinical_trials_user_agent: str = Field(
        default="clinical-trial-visualization-agent/0.1",
        validation_alias="CLINICAL_TRIALS_USER_AGENT",
    )
    aggregation_top_n: int = Field(
        default=15,
        validation_alias="AGGREGATION_TOP_N",
        description=(
            "Central agent/API limit (from .env): max aggregation buckets, trial list "
            "page_size, and source trials attached to chart responses"
        ),
    )
    aggregation_top_n_min: int = Field(default=5, validation_alias="AGGREGATION_TOP_N_MIN")
    aggregation_top_n_max: int = Field(default=100, validation_alias="AGGREGATION_TOP_N_MAX")
    agent_tool_max_trials: int = Field(
        default=10,
        validation_alias="AGENT_TOOL_MAX_TRIALS",
        description="Max trial rows returned in search_clinical_trials tool output (TPM guard)",
    )
    agent_tool_max_title_chars: int = Field(
        default=120,
        validation_alias="AGENT_TOOL_MAX_TITLE_CHARS",
        description="Truncate trial titles in tool output to this length",
    )
    agent_tool_max_conditions: int = Field(
        default=2,
        validation_alias="AGENT_TOOL_MAX_CONDITIONS",
        description="Max condition strings per trial in tool output",
    )
    chart_pie_max_buckets: int = Field(
        default=6,
        validation_alias="CHART_PIE_MAX_BUCKETS",
        description="Use pie/donut instead of bar when bucket count is at most this value",
    )
    chat_context_max_messages: int = Field(
        default=6,
        validation_alias="CHAT_CONTEXT_MAX_MESSAGES",
        description="Max prior chat messages sent to the agent for multi-turn context (0 disables)",
    )

    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    venv_dir: str = Field(default=".venv", validation_alias="VENV_DIR")
    require_venv: bool | None = Field(
        default=None,
        validation_alias="REQUIRE_VENV",
        description="When unset, requires project .venv in development only",
    )

    @field_validator("clinical_trials_max_page_size")
    @classmethod
    def validate_page_size(cls, value: int) -> int:
        return min(max(value, 1), 1000)

    @field_validator("clinical_trials_scan_page_size")
    @classmethod
    def validate_scan_page_size(cls, value: int) -> int:
        return min(max(value, 1), 1000)

    @field_validator("chart_pie_max_buckets")
    @classmethod
    def validate_chart_pie_max_buckets(cls, value: int) -> int:
        return min(max(value, 2), 20)

    @field_validator("chat_context_max_messages")
    @classmethod
    def validate_chat_context_max_messages(cls, value: int) -> int:
        return min(max(value, 0), 50)

    @field_validator("agent_tool_max_trials")
    @classmethod
    def validate_agent_tool_max_trials(cls, value: int) -> int:
        return min(max(value, 1), 25)

    @field_validator("agent_tool_max_title_chars")
    @classmethod
    def validate_agent_tool_max_title_chars(cls, value: int) -> int:
        return min(max(value, 40), 300)

    @field_validator("agent_tool_max_conditions")
    @classmethod
    def validate_agent_tool_max_conditions(cls, value: int) -> int:
        return min(max(value, 1), 5)

    @model_validator(mode="after")
    def clamp_aggregation_top_n(self) -> Settings:
        low = self.aggregation_top_n_min
        high = self.aggregation_top_n_max
        clamped = min(max(self.aggregation_top_n, low), high)
        if clamped != self.aggregation_top_n:
            self.aggregation_top_n = clamped
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def require_local_venv(self) -> bool:
        if self.require_venv is not None:
            return self.require_venv
        return self.is_development

    @property
    def uvicorn_reload(self) -> bool:
        return self.is_development

    def clamp_agent_trial_limit(self, page_size: int | None = None) -> int:
        """Default and cap for trials/buckets exposed to the agent (AGGREGATION_TOP_N)."""
        requested = page_size if page_size is not None else self.aggregation_top_n
        return min(max(requested, 1), self.aggregation_top_n)

    def clamp_tool_trial_limit(self, page_size: int | None = None) -> int:
        """Stricter cap on trials serialised in tool results to reduce TPM usage."""
        return min(self.clamp_agent_trial_limit(page_size), self.agent_tool_max_trials)

    def venv_python(self, project_root: Path) -> Path:
        if sys.platform == "win32":
            return project_root / self.venv_dir / "Scripts" / "python.exe"
        return project_root / self.venv_dir / "bin" / "python"

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


def ensure_project_venv(project_root: Path) -> None:
    """Re-exec into the configured project venv for local development."""
    settings = get_settings()
    if not settings.require_local_venv:
        return

    venv_python = settings.venv_python(project_root)
    current_python = Path(sys.executable).resolve()
    reexec_done = os.environ.get(_VENV_REEXEC_ENV) == "1"

    if not venv_python.is_file():
        raise SystemExit(
            f"Project virtualenv required but not found at {venv_python}.\n"
            f"Configured VENV_DIR={settings.venv_dir!r} (ENVIRONMENT={settings.environment}).\n"
            "Create it with: uv sync"
        )

    if reexec_done:
        if current_python != venv_python.resolve():
            raise SystemExit(
                "This app must run with the project virtualenv in development.\n"
                f"Expected: {venv_python}\n"
                f"Current:  {current_python}\n"
                f"Start with: {venv_python} main.py --serve"
            )
        return

    if current_python == venv_python.resolve():
        os.environ[_VENV_REEXEC_ENV] = "1"
        return

    env = os.environ.copy()
    env[_VENV_REEXEC_ENV] = "1"
    os.execve(str(venv_python), [str(venv_python), *sys.argv], env)
