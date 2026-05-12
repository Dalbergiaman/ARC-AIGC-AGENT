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
    IMAGE_RAG_MCP_SERVER: str = str(_REPO_ROOT / "image-rag-mcp" / "server.py")
    IMAGE_RAG_MCP_PYTHON: str = str(_REPO_ROOT / "image-rag-mcp" / ".venv" / "bin" / "python")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
