from sqlalchemy import inspect, text


def ensure_legacy_schema_compatibility(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "sessions" not in inspector.get_table_names():
        return

    session_columns = {column["name"] for column in inspector.get_columns("sessions")}
    sync_conn.execute(
        text(
            "ALTER TABLE sessions "
            "ADD COLUMN IF NOT EXISTS title VARCHAR(255) NOT NULL DEFAULT 'Unnamed Chat'"
        )
    )
    sync_conn.execute(
        text("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS workspace_state JSON")
    )

    if "generation_tasks" in inspector.get_table_names():
        generation_columns = {column["name"] for column in inspector.get_columns("generation_tasks")}
        if "task_id" not in generation_columns:
            sync_conn.execute(text("ALTER TABLE generation_tasks ADD COLUMN IF NOT EXISTS task_id VARCHAR(255)"))
        if "negative_prompt" not in generation_columns:
            sync_conn.execute(text("ALTER TABLE generation_tasks ADD COLUMN IF NOT EXISTS negative_prompt TEXT"))
        if "provider" not in generation_columns:
            sync_conn.execute(text("ALTER TABLE generation_tasks ADD COLUMN IF NOT EXISTS provider VARCHAR(50)"))
        if "score" not in generation_columns:
            sync_conn.execute(text("ALTER TABLE generation_tasks ADD COLUMN IF NOT EXISTS score DOUBLE PRECISION"))
        if "raw_response" not in generation_columns:
            sync_conn.execute(text("ALTER TABLE generation_tasks ADD COLUMN IF NOT EXISTS raw_response JSON"))
