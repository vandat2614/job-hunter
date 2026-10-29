from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://jobhunter:jobhunter@postgres:5432/notifications"
    kafka_bootstrap: str = "kafka:9092"
    telegram_bot_token: str = ""  # empty = dry-run mode (log only)
    telegram_api_base: str = "https://api.telegram.org"


settings = Settings()
