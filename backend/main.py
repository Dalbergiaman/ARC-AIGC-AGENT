from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from agent.checkpointer import get_conn_string, init_checkpointer
from agent.graph import compile_graph
from api.routes.chat import router as chat_router
from api.routes.dashboard import router as dashboard_router
from api.routes.session import router as session_router
from api.routes.upload import router as upload_router
from config import settings
from core.observability import configure_langfuse_from_dashboard, flush_langfuse
from models.database import engine
from models.schema_guard import ensure_legacy_schema_compatibility
from models.schemas import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.langfuse_enabled = configure_langfuse_from_dashboard()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ensure_legacy_schema_compatibility)

    async with AsyncPostgresSaver.from_conn_string(get_conn_string()) as saver:
        await init_checkpointer(saver)
        app.state.graph = compile_graph(saver)
        yield

    flush_langfuse()
    await engine.dispose()


app = FastAPI(title="AIGC Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_router)
app.include_router(dashboard_router)
app.include_router(session_router)
app.include_router(upload_router)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


if settings.STORAGE == "local":
    import os

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    app.mount("/static/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
