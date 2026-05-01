from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from services.storage_service import save_upload


router = APIRouter(prefix="/api", tags=["upload"])


class UploadResponse(BaseModel):
    file_id: str
    url: str


@router.post("/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)) -> UploadResponse:
    try:
        file_id, url = await save_upload(file)
        return UploadResponse(file_id=file_id, url=url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
