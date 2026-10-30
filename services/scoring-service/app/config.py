from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://jobhunter:jobhunter@postgres:5432/scoring"
    kafka_bootstrap: str = "kafka:9092"
    ollama_url: str = "http://ollama:11434"
    llm_model: str = "qwen2.5:3b"
    llm_timeout: float = 240  # seconds per attempt; CPU-only inference is slow
    llm_attempts: int = 2


settings = Settings()
