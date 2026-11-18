from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "HireTrack"
    database_url: str
    db_echo: bool = False

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # Browser origins allowed to call the API (set as a JSON list in .env).
    cors_origins: list[str] = ["http://localhost:3000"]

    # AI. "fake" runs without an API key (offline development and tests).
    llm_provider: Literal["anthropic", "fake"] = "anthropic"
    anthropic_api_key: str | None = None
    llm_model: str = "claude-haiku-5-5"
    llm_timeout_seconds: float = 30.0


settings = Settings()
