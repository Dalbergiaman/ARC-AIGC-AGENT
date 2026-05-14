import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from services import session_service


class TestSessionService(unittest.IsolatedAsyncioTestCase):
    async def test_get_session_returns_scalar_result(self):
        expected = SimpleNamespace(id=uuid.uuid4())
        scalar_result = SimpleNamespace(scalar_one_or_none=lambda: expected)
        db = SimpleNamespace(execute=AsyncMock(return_value=scalar_result))

        result = await session_service.get_session(db, expected.id)

        self.assertIs(result, expected)
        db.execute.assert_awaited_once()

    async def test_list_sessions_returns_latest_first_from_query_result(self):
        newer = SimpleNamespace(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
        older = SimpleNamespace(
            id=uuid.uuid4(),
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        scalar_result = SimpleNamespace(all=lambda: [newer, older])
        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: scalar_result)))

        result = await session_service.list_sessions(db)

        self.assertEqual(result, [newer, older])
        db.execute.assert_awaited_once()

    async def test_update_design_state_commits_and_refreshes_session(self):
        session = SimpleNamespace(id=uuid.uuid4(), design_state=None)
        db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

        with patch.object(session_service, "get_session", AsyncMock(return_value=session)) as mocked_get:
            updated = await session_service.update_design_state(db, session.id, {"style": "modern"})

        self.assertIs(updated, session)
        self.assertEqual(session.design_state, {"style": "modern"})
        mocked_get.assert_awaited_once_with(db, session.id)
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(session)

    async def test_update_session_title_commits_and_refreshes_session(self):
        session = SimpleNamespace(id=uuid.uuid4(), title="Unnamed Chat")
        db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

        with patch.object(session_service, "get_session", AsyncMock(return_value=session)) as mocked_get:
            updated = await session_service.update_session_title(db, session.id, "Modern Villa")

        self.assertIs(updated, session)
        self.assertEqual(session.title, "Modern Villa")
        mocked_get.assert_awaited_once_with(db, session.id)
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(session)

    async def test_update_workspace_state_commits_and_refreshes_session(self):
        session = SimpleNamespace(id=uuid.uuid4(), workspace_state=None)
        db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

        with patch.object(session_service, "get_session", AsyncMock(return_value=session)) as mocked_get:
            updated = await session_service.update_workspace_state(db, session.id, {"custom_description": "abc"})

        self.assertIs(updated, session)
        self.assertEqual(session.workspace_state, {"custom_description": "abc"})
        mocked_get.assert_awaited_once_with(db, session.id)
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(session)

    async def test_update_annotated_image_state_preserves_layered_workspace(self):
        session = SimpleNamespace(
            id=uuid.uuid4(),
            workspace_state={"prompt_draft": {"llm_description": "modern villa"}},
        )
        db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
        annotated_image = {
            "file_id": "anno-1",
            "url": "/static/uploads/anno.png",
            "note": "入口换材质",
            "sent": True,
        }

        with patch.object(session_service, "get_session", AsyncMock(return_value=session)) as mocked_get:
            updated = await session_service.update_annotated_image_state(
                db,
                session.id,
                annotated_image,
            )

        self.assertIs(updated, session)
        self.assertEqual(session.workspace_state["prompt_draft"], {"llm_description": "modern villa"})
        self.assertEqual(session.workspace_state["annotated_image"], annotated_image)
        mocked_get.assert_awaited_once_with(db, session.id)
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(session)

    async def test_update_annotated_image_state_wraps_legacy_prompt_draft(self):
        session = SimpleNamespace(
            id=uuid.uuid4(),
            workspace_state={"keywords": {}, "llm_description": "legacy"},
        )
        db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

        with patch.object(session_service, "get_session", AsyncMock(return_value=session)):
            await session_service.update_annotated_image_state(
                db,
                session.id,
                {"file_id": "anno-1", "url": "/static/uploads/anno.png", "note": ""},
            )

        self.assertEqual(session.workspace_state["prompt_draft"]["llm_description"], "legacy")
        self.assertEqual(session.workspace_state["annotated_image"]["file_id"], "anno-1")

    async def test_list_reference_images_returns_query_result(self):
        item = SimpleNamespace(id=uuid.uuid4())
        scalar_result = SimpleNamespace(all=lambda: [item])
        db = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: scalar_result))
        )

        result = await session_service.list_reference_images(db, uuid.uuid4())

        self.assertEqual(result, [item])
        db.execute.assert_awaited_once()

    async def test_list_generation_tasks_returns_query_result(self):
        item = SimpleNamespace(id=uuid.uuid4())
        scalar_result = SimpleNamespace(all=lambda: [item])
        db = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: scalar_result))
        )

        result = await session_service.list_generation_tasks(db, uuid.uuid4())

        self.assertEqual(result, [item])
        db.execute.assert_awaited_once()

    async def test_delete_session_returns_false_when_missing(self):
        db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())

        with patch.object(session_service, "get_session", AsyncMock(return_value=None)) as mocked_get:
            deleted = await session_service.delete_session(db, uuid.uuid4())

        self.assertFalse(deleted)
        mocked_get.assert_awaited_once()
        db.execute.assert_not_called()
        db.commit.assert_not_called()

    async def test_delete_session_removes_related_records_and_commits(self):
        session = SimpleNamespace(id=uuid.uuid4())
        db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())

        with patch.object(session_service, "get_session", AsyncMock(return_value=session)) as mocked_get:
            deleted = await session_service.delete_session(db, session.id)

        self.assertTrue(deleted)
        mocked_get.assert_awaited_once_with(db, session.id)
        self.assertEqual(db.execute.await_count, 4)
        db.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
