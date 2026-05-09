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


async def update_workspace_state(
    db: AsyncSession, session_id: uuid.UUID, workspace_state: dict | None
) -> Session | None:
    session = await get_session(db, session_id)
    if session is None:
        return None

    session.workspace_state = workspace_state
    await db.commit()
    await db.refresh(session)
    return session


async def upsert_reference_images(
    db: AsyncSession,
    session_id: uuid.UUID,
    reference_images: list[dict],
) -> list[ReferenceImage]:
    existing_result = await db.execute(
        select(ReferenceImage).where(ReferenceImage.session_id == session_id)
    )
    existing_by_file_id = {item.file_id: item for item in existing_result.scalars().all()}
    seen: set[str] = set()

    for item in reference_images:
        file_id = str(item.get("file_id") or item.get("fileId") or "").strip()
        if not file_id:
            continue
        seen.add(file_id)
        payload = item.get("analysis")
        if payload is None:
            payload = {
                "intent": item.get("intent"),
                "note": item.get("note", ""),
                "sent": item.get("sent", False),
            }
        existing = existing_by_file_id.get(file_id)
        if existing is None:
            existing = ReferenceImage(
                session_id=session_id,
                file_id=file_id,
                url=str(item.get("url") or ""),
                analysis=payload,
            )
            db.add(existing)
            existing_by_file_id[file_id] = existing
        else:
            existing.url = str(item.get("url") or existing.url)
            existing.analysis = payload

    if seen:
        result = await db.execute(select(ReferenceImage).where(ReferenceImage.session_id == session_id))
        items = list(result.scalars().all())
    else:
        items = []

    await db.commit()
    return items


async def create_generation_task(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    task_id: str | None,
    prompt: str,
    negative_prompt: str | None,
    provider: str | None,
    image_url: str | None = None,
    status: str = "pending",
    score: float | None = None,
    raw_response: dict | None = None,
) -> GenerationTask:
    task = GenerationTask(
        session_id=session_id,
        task_id=task_id,
        prompt=prompt,
        negative_prompt=negative_prompt,
        provider=provider,
        image_url=image_url,
        status=status,
        score=score,
        raw_response=raw_response,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def list_reference_images(
    db: AsyncSession, session_id: uuid.UUID
) -> list[ReferenceImage]:
    result = await db.execute(
        select(ReferenceImage)
        .where(ReferenceImage.session_id == session_id)
        .order_by(ReferenceImage.created_at.asc())
    )
    return list(result.scalars().all())


async def list_generation_tasks(
    db: AsyncSession, session_id: uuid.UUID
) -> list[GenerationTask]:
    result = await db.execute(
        select(GenerationTask)
        .where(GenerationTask.session_id == session_id)
        .order_by(GenerationTask.created_at.asc())
    )
    return list(result.scalars().all())


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
