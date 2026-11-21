from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "British Auction RFQ API"

    database_url: str = "postgresql+asyncpg://rfq:rfq@localhost:5432/rfq"
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # how often the close task runs
    close_sweep_interval_seconds: float = 2.0

    demo_enabled: bool = True


settings = Settings()
