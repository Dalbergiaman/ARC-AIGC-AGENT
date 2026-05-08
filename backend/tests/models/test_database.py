from unittest.mock import patch


def test_engine_uses_connection_health_checks() -> None:
    with patch("sqlalchemy.ext.asyncio.create_async_engine") as create_engine:
        import importlib
        import models.database

        importlib.reload(models.database)

    _, kwargs = create_engine.call_args
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_recycle"] == 1800
