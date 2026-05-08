"""Langfuse observability helpers.

This module keeps Langfuse optional at runtime: empty dashboard credentials or
SDK errors should not break the Agent execution path.
"""
from __future__ import annotations

import os
from contextlib import nullcontext
from functools import wraps
from typing import Any, Callable

from services import dashboard_service

try:
    import langfuse
except Exception:  # pragma: no cover - dependency is optional at runtime
    langfuse = None  # type: ignore[assignment]


def configure_langfuse_from_dashboard() -> bool:
    """Configure Langfuse SDK from dashboard.yaml.

    Returns True when credentials are present. When credentials are absent,
    tracing is explicitly disabled to avoid noisy authentication warnings.
    """
    config = dashboard_service.get_config().get("langfuse", {})
    public_key = (config.get("public_key") or "").strip()
    secret_key = (config.get("secret_key") or "").strip()
    host = (config.get("host") or "").strip()

    if not public_key or not secret_key:
        os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
        return False

    os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
    os.environ["LANGFUSE_SECRET_KEY"] = secret_key
    if host:
        os.environ["LANGFUSE_BASE_URL"] = host
        os.environ["LANGFUSE_HOST"] = host
    os.environ["LANGFUSE_TRACING_ENABLED"] = "true"
    return True


def observe(
    *,
    name: str,
    as_type: str = "span",
    capture_input: bool = False,
    capture_output: bool = False,
) -> Callable:
    """Return a Langfuse observe decorator, or a no-op decorator if unavailable."""
    if langfuse is None:
        return lambda func: func
    return langfuse.observe(
        name=name,
        as_type=as_type,  # type: ignore[arg-type]
        capture_input=capture_input,
        capture_output=capture_output,
    )


def update_current_span(
    *,
    input: Any | None = None,
    output: Any | None = None,
    metadata: Any | None = None,
    level: str | None = None,
    status_message: str | None = None,
) -> None:
    if langfuse is None:
        return
    try:
        langfuse.get_client().update_current_span(
            input=input,
            output=output,
            metadata=metadata,
            level=level,  # type: ignore[arg-type]
            status_message=status_message,
        )
    except Exception:
        pass


def update_current_generation(
    *,
    input: Any | None = None,
    output: Any | None = None,
    metadata: Any | None = None,
    model: str | None = None,
    level: str | None = None,
    status_message: str | None = None,
) -> None:
    if langfuse is None:
        return
    try:
        langfuse.get_client().update_current_generation(
            input=input,
            output=output,
            metadata=metadata,
            model=model,
            level=level,  # type: ignore[arg-type]
            status_message=status_message,
        )
    except Exception:
        pass


def start_observation(
    *,
    name: str,
    as_type: str = "span",
    input: Any | None = None,
    metadata: Any | None = None,
):
    """Start a current Langfuse observation context, or return a no-op context."""
    if langfuse is None:
        return nullcontext()
    try:
        return langfuse.get_client().start_as_current_observation(
            name=name,
            as_type=as_type,  # type: ignore[arg-type]
            input=input,
            metadata=metadata,
        )
    except Exception:
        return nullcontext()


def set_current_trace_io(*, input: Any | None = None, output: Any | None = None) -> None:
    if langfuse is None:
        return
    try:
        langfuse.get_client().set_current_trace_io(input=input, output=output)
    except Exception:
        pass


def flush_langfuse() -> None:
    if langfuse is None:
        return
    try:
        langfuse.get_client().flush()
    except Exception:
        pass


def message_preview(content: Any, *, limit: int = 600) -> str:
    text = content if isinstance(content, str) else str(content)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"
