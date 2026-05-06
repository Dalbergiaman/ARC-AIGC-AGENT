from sqlalchemy import inspect, text


def ensure_legacy_schema_compatibility(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "sessions" not in inspector.get_table_names():
        return

    session_columns = {column["name"] for column in inspector.get_columns("sessions")}
    if "title" in session_columns:
        return

    sync_conn.execute(
        text(
            "ALTER TABLE sessions "
            "ADD COLUMN IF NOT EXISTS title VARCHAR(255) NOT NULL DEFAULT 'Unnamed Chat'"
        )
    )
