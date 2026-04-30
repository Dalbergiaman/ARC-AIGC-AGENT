from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import settings
from models.database import engine
from models.schemas import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="AIGC Agent", lifespan=lifespan)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


if settings.STORAGE == "local":
    import os

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    app.mount("/static/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
