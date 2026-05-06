import uuid

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm.client import LLMClient
from services.message_service import get_messages
from services.session_service import DEFAULT_SESSION_TITLE, get_session, update_session_title


_llm = LLMClient()


async def maybe_generate_session_title(db: AsyncSession, session_id: uuid.UUID) -> str | None:
    session = await get_session(db, session_id)
    if session is None:
        return None

    current_title = (session.title or "").strip()
    if current_title and current_title != DEFAULT_SESSION_TITLE:
        return current_title

    messages = await get_messages(db, session_id, limit=10)
    first_user = next((message.content.strip() for message in messages if message.role == "user" and message.content.strip()), "")
    first_assistant = next(
        (message.content.strip() for message in messages if message.role == "assistant" and message.content.strip()),
        "",
    )

    if not first_user or not first_assistant:
        return current_title or DEFAULT_SESSION_TITLE

    prompt = (
        "请基于这轮建筑效果图对话，为会话生成一个简短标题。"
        "要求：1) 4到8个英文单词或4到12个中文字符；2) 不要加引号；3) 不要使用标点结尾；4) 只返回标题本身。"
    )

    raw_title = await _llm.ainvoke(
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=(
                    f"用户首条消息：{first_user}\n"
                    f"助手首条回复：{first_assistant}"
                )
            ),
        ]
    )
    title = _normalize_title(raw_title)
    if not title:
        return current_title or DEFAULT_SESSION_TITLE

    updated = await update_session_title(db, session_id, title)
    return updated.title if updated else title


def _normalize_title(raw_title: str) -> str:
    title = raw_title.strip()
    if not title:
        return ""
    title = title.splitlines()[0].strip().strip("\"'")
    return title[:60]
