from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://jobhunter:jobhunter@postgres:5432/matching"
    kafka_bootstrap: str = "kafka:9092"


settings = Settings()
