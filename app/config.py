from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    api_key: str
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    rate_limit_messages: int = 20
    rate_limit_window_seconds: int = 3600
    max_history_messages: int = 20
    input_cost_per_1m: float = 0.15
    output_cost_per_1m: float = 0.60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
