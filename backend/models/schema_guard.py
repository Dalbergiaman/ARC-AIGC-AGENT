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

    # Migrate flat PromptDraft -> layered {prompt_draft, ...}
    # Old shape: {keywords, llm_description, custom_description, negative_prompt, prompt_template}
    # New shape: {prompt_draft: {...}, rag_image, control_image, annotated_image}
    sync_conn.execute(
        text(
            """
            UPDATE sessions
            SET workspace_state = jsonb_build_object('prompt_draft', workspace_state::jsonb)
            WHERE workspace_state IS NOT NULL
              AND workspace_state::jsonb ? 'keywords'
              AND NOT (workspace_state::jsonb ? 'prompt_draft')
            """
        )
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
        if "stored_in_library" not in generation_columns:
            sync_conn.execute(text("ALTER TABLE generation_tasks ADD COLUMN IF NOT EXISTS stored_in_library BOOLEAN NOT NULL DEFAULT FALSE"))
