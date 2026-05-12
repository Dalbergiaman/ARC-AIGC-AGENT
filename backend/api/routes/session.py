import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session as get_db
from services.message_service import get_messages
from services.session_service import (
    create_session,
    delete_session,
    get_session,
    list_generation_tasks,
    list_reference_images,
    list_sessions,
)


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionResponse(BaseModel):
    id: uuid.UUID
    title: str = "Unnamed Chat"
    design_state: dict | None
    workspace_state: dict | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReferenceImageResponse(BaseModel):
    id: uuid.UUID
    file_id: str
    url: str
    analysis: dict | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class GenerationTaskResponse(BaseModel):
    id: uuid.UUID
    task_id: str | None = None
    prompt: str
    negative_prompt: str | None = None
    provider: str | None = None
    image_url: str | None = None
    status: str
    score: float | None = None
    raw_response: dict | None = None
    stored_in_library: bool = False
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SessionDetailResponse(SessionResponse):
    messages: list[MessageResponse]
    reference_images: list[ReferenceImageResponse] = []
    generation_tasks: list[GenerationTaskResponse] = []


@router.post("", response_model=SessionResponse, status_code=201)
async def create_new_session(db: AsyncSession = Depends(get_db)) -> SessionResponse:
    session = await create_session(db)
    return SessionResponse.model_validate(session)


@router.get("", response_model=list[SessionResponse])
async def list_session_items(db: AsyncSession = Depends(get_db)) -> list[SessionResponse]:
    sessions = await list_sessions(db)
    return [SessionResponse.model_validate(session) for session in sessions]


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> SessionDetailResponse:
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = await get_messages(db, session_id, limit=100)
    reference_images = await list_reference_images(db, session_id)
    generation_tasks = await list_generation_tasks(db, session_id)
    return SessionDetailResponse(
        **SessionResponse.model_validate(session).model_dump(),
        messages=[MessageResponse.model_validate(message) for message in messages],
        reference_images=[ReferenceImageResponse.model_validate(item) for item in reference_images],
        generation_tasks=[GenerationTaskResponse.model_validate(item) for item in generation_tasks],
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session_item(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    deleted = await delete_session(db, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
