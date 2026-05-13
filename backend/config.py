from pathlib import Path

from pydantic_settings import BaseSettings

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aigc_agent"
    REDIS_URL: str = "redis://localhost:6379/0"
    STORAGE: str = "local"
    UPLOAD_DIR: str = "uploads"
    GENERATED_DIR: str = "generated"
    IMAGE_LIBRARY_DIR: str = str(_REPO_ROOT / "image-rag-mcp" / "library_images")
    IMAGE_LIBRARY_STORAGE: str = "local"
    IMAGE_LIBRARY_MINIO_ENDPOINT: str = "http://localhost:9000"
    IMAGE_LIBRARY_MINIO_PUBLIC_ENDPOINT: str = "http://localhost:9000"
    IMAGE_LIBRARY_MINIO_ACCESS_KEY: str = "minioadmin"
    IMAGE_LIBRARY_MINIO_SECRET_KEY: str = "minioadmin"
    IMAGE_LIBRARY_MINIO_BUCKET: str = "image-library"
    IMAGE_RAG_MCP_SERVER: str = str(_REPO_ROOT / "image-rag-mcp" / "server.py")
    IMAGE_RAG_MCP_PYTHON: str = str(_REPO_ROOT / "image-rag-mcp" / ".venv" / "bin" / "python")
    RAG_BLOCKING_ENABLED: bool = True
    RAG_BLOCKING_TIMEOUT: int = 600

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
