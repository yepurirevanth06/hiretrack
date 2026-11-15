from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "HireTrack"
    database_url: str
    db_echo: bool = False

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30


settings = Settings()
