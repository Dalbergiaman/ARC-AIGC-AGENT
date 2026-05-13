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
    "embedding": {
        "provider": "volcengine",
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
        {"id": "bailian", "label": "Bailian", "models": ["wan2.7-image-pro"]},
        {
            "id": "volcengine",
            "label": "Volcengine",
            "models": ["doubao-seedream-5-0-260128", "doubao-seedream-4-5-251128"],
        },
        {
            "id": "grsai",
            "label": "GrsAI",
            "models": ["gpt-image-2", "nano-banana-pro"],
        },
    ],
    "embedding": [
        {
            "id": "volcengine",
            "label": "Volcengine",
            "models": ["doubao-embedding", "doubao-embedding-vision-251215"],
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
    config = _deep_merge(config, raw)
    _normalize_image_provider_model(config)
    return config


def _normalize_image_provider_model(config: dict[str, Any]) -> None:
    image_config = config.get("image_provider")
    if not isinstance(image_config, dict):
        return

    provider_id = image_config.get("provider")
    provider = next(
        (item for item in PROVIDERS["image_provider"] if item["id"] == provider_id),
        None,
    )
    if provider is None:
        provider = PROVIDERS["image_provider"][0]
        image_config["provider"] = provider["id"]

    models = provider.get("models") or []
    if models and image_config.get("model") not in models:
        image_config["model"] = models[0]


def get_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return deepcopy(DEFAULT_CONFIG)

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)

    return _normalize_config(raw)


def update_config(patch: dict[str, Any]) -> dict[str, Any]:
    current = get_config()
    updated = _deep_merge(current, patch)
    _normalize_image_provider_model(updated)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        yaml.safe_dump(updated, file, allow_unicode=True, sort_keys=False)

    return updated


def get_providers() -> dict[str, Any]:
    return deepcopy(PROVIDERS)


if __name__ == "__main__":
    config = get_config()
    providers = get_providers()

    print("Dashboard config sections:", ", ".join(config.keys()))
    print("LLM provider:", config["llm"]["provider"], config["llm"]["model"])
    print(
        "Image provider:",
        config["image_provider"]["provider"],
        config["image_provider"]["model"],
    )
    print("Embedding provider:", config["embedding"]["provider"])
    print(
        "Image provider options:",
        ", ".join(item["id"] for item in providers["image_provider"]),
    )
    print(
        "Embedding provider options:",
        ", ".join(item["id"] for item in providers["embedding"]),
    )
