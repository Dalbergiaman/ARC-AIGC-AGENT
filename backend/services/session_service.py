import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import Session


async def create_session(db: AsyncSession) -> Session:
    session = Session()
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> Session | None:
    result = await db.execute(select(Session).where(Session.id == session_id))
    return result.scalar_one_or_none()


async def list_sessions(db: AsyncSession, limit: int = 20) -> list[Session]:
    result = await db.execute(
        select(Session).order_by(Session.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


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
