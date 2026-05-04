from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "dashboard.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    "llm": {
        "provider": "bailian",
        "model": "qwen-vl-max",
        "api_key": "",
    },
    "image_provider": {
        "provider": "bailian",
        "model": "wan2.7-image-pro",
        "api_key": "",
    },
    "langfuse": {
        "host": "http://localhost:3000",
        "public_key": "",
        "secret_key": "",
    },
}

PROVIDERS: dict[str, Any] = {
    "llm": [
        {
            "id": "bailian",
            "label": "Bailian",
            "models": ["qwen-vl-max", "qwen-vl-plus"],
        },
        {
            "id": "volcengine",
            "label": "Volcengine",
            "models": ["doubao-1.5-vision-pro-32k"],
        },
    ],
    "image_provider": [
        {"id": "bailian", "label": "Bailian", "models": ["wanx2.1-t2i-turbo"]},
        {
            "id": "volcengine",
            "label": "Volcengine",
            "models": ["doubao-seedream-3-0-t2i-250415"],
        },
        {
            "id": "openrouter",
            "label": "OpenRouter",
            "models": ["google/gemini-2.5-flash-image-preview"],
        },
    ],
}


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    if not isinstance(raw, dict):
        return config
    return _deep_merge(config, raw)


def get_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return deepcopy(DEFAULT_CONFIG)

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)

    return _normalize_config(raw)


def update_config(patch: dict[str, Any]) -> dict[str, Any]:
    current = get_config()
    updated = _deep_merge(current, patch)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        yaml.safe_dump(updated, file, allow_unicode=True, sort_keys=False)

    return updated


def get_providers() -> dict[str, Any]:
    return deepcopy(PROVIDERS)
