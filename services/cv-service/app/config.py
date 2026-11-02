from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://jobhunter:jobhunter@postgres:5432/cvs"
    kafka_bootstrap: str = "kafka:9092"



    cv_extraction: str = "real"  # "mock" freezes extraction: every upload stores MOCK_CV_TEXT
settings = Settings()
