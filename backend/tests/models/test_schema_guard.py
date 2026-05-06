import unittest
from unittest.mock import MagicMock, patch

from models.schema_guard import ensure_legacy_schema_compatibility


class TestSchemaGuard(unittest.TestCase):
    def test_skip_when_sessions_table_missing(self):
        sync_conn = MagicMock()
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["messages"]

        with patch("models.schema_guard.inspect", return_value=inspector):
            ensure_legacy_schema_compatibility(sync_conn)

        inspector.get_columns.assert_not_called()
        sync_conn.execute.assert_not_called()

    def test_skip_when_title_column_exists(self):
        sync_conn = MagicMock()
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["sessions"]
        inspector.get_columns.return_value = [{"name": "id"}, {"name": "title"}]

        with patch("models.schema_guard.inspect", return_value=inspector):
            ensure_legacy_schema_compatibility(sync_conn)

        inspector.get_columns.assert_called_once_with("sessions")
        sync_conn.execute.assert_not_called()

    def test_add_title_column_when_missing(self):
        sync_conn = MagicMock()
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["sessions"]
        inspector.get_columns.return_value = [{"name": "id"}, {"name": "design_state"}]

        with patch("models.schema_guard.inspect", return_value=inspector):
            ensure_legacy_schema_compatibility(sync_conn)

        inspector.get_columns.assert_called_once_with("sessions")
        sync_conn.execute.assert_called_once()
        sql_text = str(sync_conn.execute.call_args.args[0])
        self.assertIn("ALTER TABLE sessions", sql_text)
        self.assertIn("ADD COLUMN IF NOT EXISTS title", sql_text)


if __name__ == "__main__":
    unittest.main()
