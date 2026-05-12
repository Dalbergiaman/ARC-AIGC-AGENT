from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from agent.checkpointer import get_conn_string, init_checkpointer
from agent.graph import compile_graph, set_mcp_client
from api.routes.chat import router as chat_router
from api.routes.dashboard import router as dashboard_router
from api.routes.gallery import router as gallery_router
from api.routes.library import router as library_router
from api.routes.session import router as session_router
from api.routes.styles import router as styles_router
from api.routes.upload import router as upload_router
from config import settings
from core.observability import configure_langfuse_from_dashboard, flush_langfuse
from models.database import engine
from models.schema_guard import ensure_legacy_schema_compatibility
from models.schemas import Base


def _build_mcp_client() -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "image-rag": {
                "command": settings.IMAGE_RAG_MCP_PYTHON,
                "args": [settings.IMAGE_RAG_MCP_SERVER],
                "transport": "stdio",
            },
        }
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.langfuse_enabled = configure_langfuse_from_dashboard()
    app.state.mcp_client = _build_mcp_client()
    set_mcp_client(app.state.mcp_client)

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
app.include_router(gallery_router)
app.include_router(library_router)
app.include_router(session_router)
app.include_router(styles_router)
app.include_router(upload_router)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


if settings.STORAGE == "local":
    import os

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.GENERATED_DIR, exist_ok=True)
    os.makedirs(settings.IMAGE_LIBRARY_DIR, exist_ok=True)
    app.mount("/static/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
    app.mount("/static/generated", StaticFiles(directory=settings.GENERATED_DIR), name="generated")
    app.mount("/static/library", StaticFiles(directory=settings.IMAGE_LIBRARY_DIR), name="library")
