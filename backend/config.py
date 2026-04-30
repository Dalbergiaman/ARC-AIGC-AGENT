from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aigc_agent"
    REDIS_URL: str = "redis://localhost:6379/0"
    STORAGE: str = "local"
    UPLOAD_DIR: str = "uploads"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
