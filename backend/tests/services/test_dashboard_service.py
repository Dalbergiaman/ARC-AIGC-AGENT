from pathlib import Path

import yaml

from services import dashboard_service


def test_get_config_returns_defaults_when_file_missing(tmp_path):
    config_path = tmp_path / "missing.yaml"
    original = dashboard_service.CONFIG_PATH
    dashboard_service.CONFIG_PATH = config_path
    try:
        config = dashboard_service.get_config()
    finally:
        dashboard_service.CONFIG_PATH = original

    assert config == dashboard_service.DEFAULT_CONFIG


def test_get_config_fills_missing_keys(tmp_path):
    config_path = tmp_path / "dashboard.yaml"
    config_path.write_text(
        yaml.safe_dump({"llm": {"provider": "volcengine"}}, sort_keys=False),
        encoding="utf-8",
    )

    original = dashboard_service.CONFIG_PATH
    dashboard_service.CONFIG_PATH = config_path
    try:
        config = dashboard_service.get_config()
    finally:
        dashboard_service.CONFIG_PATH = original

    assert config["llm"]["provider"] == "volcengine"
    assert config["llm"]["model"] == dashboard_service.DEFAULT_CONFIG["llm"]["model"]
    assert config["image_provider"] == dashboard_service.DEFAULT_CONFIG["image_provider"]
    assert config["langfuse"] == dashboard_service.DEFAULT_CONFIG["langfuse"]


def test_update_config_merges_patch_without_overwriting_other_fields(tmp_path):
    config_path = tmp_path / "dashboard.yaml"
    initial = {
        "llm": {
            "provider": "bailian",
            "model": "qwen-vl-max",
            "api_key": "llm-key",
        },
        "image_provider": {
            "provider": "bailian",
            "api_key": "image-key",
        },
        "langfuse": {
            "host": "http://localhost:3000",
            "public_key": "pk-1",
            "secret_key": "sk-1",
        },
    }
    config_path.write_text(yaml.safe_dump(initial, sort_keys=False), encoding="utf-8")

    original = dashboard_service.CONFIG_PATH
    dashboard_service.CONFIG_PATH = config_path
    try:
        updated = dashboard_service.update_config({"llm": {"provider": "volcengine"}})
    finally:
        dashboard_service.CONFIG_PATH = original

    assert updated["llm"]["provider"] == "volcengine"
    assert updated["llm"]["model"] == "qwen-vl-max"
    assert updated["llm"]["api_key"] == "llm-key"
    assert updated["image_provider"]["api_key"] == "image-key"


def test_write_then_read_consistent(tmp_path):
    config_path = tmp_path / "dashboard.yaml"
    original = dashboard_service.CONFIG_PATH
    dashboard_service.CONFIG_PATH = config_path

    patch = {
        "image_provider": {"provider": "openrouter", "api_key": "openrouter-key"},
        "langfuse": {"host": "http://localhost:3100"},
    }

    try:
        written = dashboard_service.update_config(patch)
        read_back = dashboard_service.get_config()
    finally:
        dashboard_service.CONFIG_PATH = original

    assert read_back == written
