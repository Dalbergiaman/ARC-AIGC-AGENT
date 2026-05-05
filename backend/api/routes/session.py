import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_session as get_db
from services.session_service import create_session, get_session


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionResponse(BaseModel):
    id: uuid.UUID
    design_state: dict | None

    model_config = {"from_attributes": True}


@router.post("", response_model=SessionResponse, status_code=201)
async def create_new_session(db: AsyncSession = Depends(get_db)) -> SessionResponse:
    session = await create_session(db)
    return SessionResponse.model_validate(session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session_detail(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> SessionResponse:
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse.model_validate(session)
