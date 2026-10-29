from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://jobhunter:jobhunter@postgres:5432/users"
    kafka_bootstrap: str = "kafka:9092"
    jwt_secret: str = "dev-only-change-me"
    jwt_expire_minutes: int = 60


settings = Settings()
