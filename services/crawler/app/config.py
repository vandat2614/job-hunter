from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kafka_bootstrap: str = "kafka:9092"
    crawl_interval_minutes: int = 60


settings = Settings()
