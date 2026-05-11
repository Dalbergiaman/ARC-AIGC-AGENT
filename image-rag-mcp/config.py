import os
from pathlib import Path
from typing import Any

import yaml


_DEFAULT_PG_DSN = "postgresql://postgres:postgres@localhost:5432/aigc_image_library"
_DEFAULT_MILVUS_HOST = "localhost"
_DEFAULT_MILVUS_PORT = "19530"
_DEFAULT_DASHBOARD_YAML = (
    Path(__file__).resolve().parent.parent / "backend" / "config" / "dashboard.yaml"
)
_DEFAULT_LIBRARY_DIR = Path(__file__).resolve().parent / "library_images"

COLLECTION_NAME = "image_library"
CAPTION_VECTOR_DIM = 2048
IMAGE_VECTOR_DIM = 2048


def get_pg_dsn() -> str:
    return os.getenv("IMAGE_LIBRARY_PG_DSN", _DEFAULT_PG_DSN)


def get_milvus_host() -> str:
    return os.getenv("MILVUS_HOST", _DEFAULT_MILVUS_HOST)


def get_milvus_port() -> str:
    return os.getenv("MILVUS_PORT", _DEFAULT_MILVUS_PORT)


def get_dashboard_yaml_path() -> Path:
    raw = os.getenv("DASHBOARD_YAML_PATH")
    return Path(raw).resolve() if raw else _DEFAULT_DASHBOARD_YAML


def get_library_dir() -> Path:
    raw = os.getenv("IMAGE_LIBRARY_DIR")
    return Path(raw).resolve() if raw else _DEFAULT_LIBRARY_DIR


def load_dashboard_config() -> dict[str, Any]:
    path = get_dashboard_yaml_path()
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw if isinstance(raw, dict) else {}


def get_embedding_api_key() -> str:
    config = load_dashboard_config()
    embedding = config.get("embedding") if isinstance(config, dict) else None
    if isinstance(embedding, dict):
        return str(embedding.get("api_key") or "")
    return ""


def get_llm_config() -> dict[str, Any]:
    config = load_dashboard_config()
    llm = config.get("llm") if isinstance(config, dict) else None
    return llm if isinstance(llm, dict) else {}


if __name__ == "__main__":
    print("PG DSN:", get_pg_dsn())
    print("Milvus:", f"{get_milvus_host()}:{get_milvus_port()}")
    print("Dashboard YAML:", get_dashboard_yaml_path())
    print("Dashboard exists:", get_dashboard_yaml_path().exists())
    print("Embedding key set:", bool(get_embedding_api_key()))
    print("LLM provider:", get_llm_config().get("provider"))
