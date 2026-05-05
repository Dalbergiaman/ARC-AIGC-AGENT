import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import Message


async def add_message(
    db: AsyncSession, session_id: uuid.UUID, role: str, content: str
) -> Message:
    message = Message(session_id=session_id, role=role, content=content)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def get_messages(
    db: AsyncSession, session_id: uuid.UUID, limit: int = 20
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    return list(reversed(messages))
