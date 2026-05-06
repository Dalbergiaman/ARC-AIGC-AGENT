import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import GenerationTask, Message, ReferenceImage, Session


DEFAULT_SESSION_TITLE = "Unnamed Chat"


async def create_session(db: AsyncSession) -> Session:
    session = Session(title=DEFAULT_SESSION_TITLE)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> Session | None:
    result = await db.execute(select(Session).where(Session.id == session_id))
    return result.scalar_one_or_none()


async def list_sessions(db: AsyncSession, limit: int | None = None) -> list[Session]:
    stmt = select(Session).order_by(Session.created_at.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_session(db: AsyncSession, session_id: uuid.UUID) -> bool:
    session = await get_session(db, session_id)
    if session is None:
        return False

    await db.execute(delete(Message).where(Message.session_id == session_id))
    await db.execute(delete(ReferenceImage).where(ReferenceImage.session_id == session_id))
    await db.execute(delete(GenerationTask).where(GenerationTask.session_id == session_id))
    await db.execute(delete(Session).where(Session.id == session_id))
    await db.commit()
    return True


async def update_session_title(
    db: AsyncSession, session_id: uuid.UUID, title: str
) -> Session | None:
    session = await get_session(db, session_id)
    if session is None:
        return None

    session.title = title.strip() or DEFAULT_SESSION_TITLE
    await db.commit()
    await db.refresh(session)
    return session


async def update_design_state(
    db: AsyncSession, session_id: uuid.UUID, design_state: dict
) -> Session | None:
    session = await get_session(db, session_id)
    if session is None:
        return None
    session.design_state = design_state
    await db.commit()
    await db.refresh(session)
    return session
