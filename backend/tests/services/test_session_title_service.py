import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from services import session_title_service


class TestSessionTitleService(unittest.IsolatedAsyncioTestCase):
    def test_normalize_title_trims_quotes_and_newlines(self):
        title = session_title_service._normalize_title('  "Modern Courtyard House"\nSecond line  ')
        self.assertEqual(title, "Modern Courtyard House")

    async def test_skip_generation_when_title_already_set(self):
        session = SimpleNamespace(id=uuid.uuid4(), title="Courtyard House")
        db = SimpleNamespace()

        with patch.object(session_title_service, "get_session", AsyncMock(return_value=session)):
            result = await session_title_service.maybe_generate_session_title(db, session.id)

        self.assertEqual(result, "Courtyard House")

    async def test_keep_default_when_first_round_not_complete(self):
        session = SimpleNamespace(id=uuid.uuid4(), title="Unnamed Chat")
        db = SimpleNamespace()

        with (
            patch.object(session_title_service, "get_session", AsyncMock(return_value=session)),
            patch.object(
                session_title_service,
                "get_messages",
                AsyncMock(return_value=[SimpleNamespace(role="user", content="帮我做个建筑方案")]),
            ),
        ):
            result = await session_title_service.maybe_generate_session_title(db, session.id)

        self.assertEqual(result, "Unnamed Chat")

    async def test_generate_title_after_first_round(self):
        session = SimpleNamespace(id=uuid.uuid4(), title="Unnamed Chat")
        db = SimpleNamespace()
        messages = [
            SimpleNamespace(role="user", content="做一个现代极简别墅效果图"),
            SimpleNamespace(role="assistant", content="好的，我先整理设计方向和材质氛围。"),
        ]

        with (
            patch.object(session_title_service, "get_session", AsyncMock(return_value=session)),
            patch.object(session_title_service, "get_messages", AsyncMock(return_value=messages)),
            patch.object(session_title_service._llm, "ainvoke", AsyncMock(return_value="Modern Minimal Villa")),
            patch.object(
                session_title_service,
                "update_session_title",
                AsyncMock(return_value=SimpleNamespace(title="Modern Minimal Villa")),
            ) as mocked_update,
        ):
            result = await session_title_service.maybe_generate_session_title(db, session.id)

        self.assertEqual(result, "Modern Minimal Villa")
        mocked_update.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
