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

    # Clean up rag_image upload copy before removing the session row
    ws = getattr(session, "workspace_state", None) or {}
    rag_image = ws.get("rag_image") if isinstance(ws, dict) else None
    if isinstance(rag_image, dict):
        rag_url = rag_image.get("image_url") or ""
        if rag_url.startswith("/static/uploads/"):
            from pathlib import Path
            from config import settings
            filename = rag_url.removeprefix("/static/uploads/")
            p = Path(settings.UPLOAD_DIR) / filename
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass

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


async def update_prompt_draft(
    db: AsyncSession, session_id: uuid.UUID, prompt_draft: dict
) -> Session | None:
    """Merge prompt_draft into the layered workspace_state, preserving other sub-keys."""
    session = await get_session(db, session_id)
    if session is None:
        return None

    existing = dict(session.workspace_state) if isinstance(session.workspace_state, dict) else {}
    # Handle legacy flat format (direct PromptDraft keys at root)
    if "keywords" in existing and "prompt_draft" not in existing:
        existing = {"prompt_draft": existing}
    existing["prompt_draft"] = prompt_draft
    session.workspace_state = existing
    await db.commit()
    await db.refresh(session)
    return session


async def update_rag_image_state(
    db: AsyncSession, session_id: uuid.UUID, rag_image: dict | None
) -> Session | None:
    """Persist the rag_image sub-key in workspace_state."""
    session = await get_session(db, session_id)
    if session is None:
        return None

    existing = dict(session.workspace_state) if isinstance(session.workspace_state, dict) else {}
    if "keywords" in existing and "prompt_draft" not in existing:
        existing = {"prompt_draft": existing}
    if rag_image is None:
        existing.pop("rag_image", None)
    else:
        existing["rag_image"] = rag_image
    session.workspace_state = existing
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


async def mark_stored_in_library(
    db: AsyncSession, session_id: uuid.UUID, task_id: str
) -> bool:
    result = await db.execute(
        select(GenerationTask)
        .where(GenerationTask.session_id == session_id)
        .where(GenerationTask.task_id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return False
    task.stored_in_library = True
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
