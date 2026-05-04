from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from services import dashboard_service


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class LLMConfigPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str | None = None
    model: str | None = None
    api_key: str | None = None


class ImageProviderConfigPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str | None = None
    model: str | None = None
    api_key: str | None = None


class LangfuseConfigPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str | None = None
    public_key: str | None = None
    secret_key: str | None = None


class DashboardConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: LLMConfigPatch | None = None
    image_provider: ImageProviderConfigPatch | None = None
    langfuse: LangfuseConfigPatch | None = None


@router.get("/config")
async def get_dashboard_config() -> dict[str, Any]:
    return dashboard_service.get_config()


@router.put("/config")
async def update_dashboard_config(payload: DashboardConfigUpdateRequest) -> dict[str, Any]:
    patch = payload.model_dump(exclude_none=True)
    return dashboard_service.update_config(patch)


@router.get("/providers")
async def get_dashboard_providers() -> dict[str, Any]:
    return dashboard_service.get_providers()
