import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))

from src.config import CACHE_TTL, SIMILARITY_TOP_K, VALKEY_URL
from src.embedder import get_embedder
from src.ingest import check_index_exists
from src.query import ask_with_sources
from src.task_manager import TaskManager
from src.valkey_cache import ValkeyCache

app_state: dict = {}


@asynccontextmanager
async def lifespan(application: FastAPI):
    get_embedder()

    cache = ValkeyCache(VALKEY_URL, ttl=CACHE_TTL)
    tasks = TaskManager()

    application.state.cache = cache
    application.state.tasks = tasks

    yield

    tasks.shutdown()
    cache.close()


app = FastAPI(
    title="Agroecology RAG API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=SIMILARITY_TOP_K, ge=1, le=20)


class AskResponse(BaseModel):
    task_id: str
    status: str


class AnswerResponse(BaseModel):
    task_id: str
    status: str
    answer: str | None = None
    sources: list[dict] | None = None
    error: str | None = None


class StatusResponse(BaseModel):
    index_ready: bool
    active_tasks: int
    cache_enabled: bool
    cache_hits: int


@app.post("/api/v1/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    if not check_index_exists():
        raise HTTPException(
            status_code=503,
            detail="Índice não encontrado. Execute: python main.py ingest",
        )

    cache = app.state.cache
    cached = cache.get(body.question)
    if cached:
        task_id = app.state.tasks.create(body.question, body.top_k)
        app.state.tasks.update(
            task_id,
            status="done",
            answer=cached["answer"],
            sources=cached.get("sources", []),
        )
        return AskResponse(task_id=task_id, status="done")

    task_id = app.state.tasks.create(body.question, body.top_k)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None, _process_task, task_id, body.question, body.top_k, cache
    )

    return AskResponse(task_id=task_id, status="processing")


@app.get("/api/v1/answer/{task_id}", response_model=AnswerResponse)
async def answer(task_id: str):
    task = app.state.tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task não encontrada ou expirada",
        )
    return AnswerResponse(
        task_id=task.task_id,
        status=task.status,
        answer=task.answer,
        sources=task.sources,
        error=task.error,
    )


@app.get("/api/v1/status", response_model=StatusResponse)
async def status():
    cache = app.state.cache
    tasks = app.state.tasks
    return StatusResponse(
        index_ready=check_index_exists(),
        active_tasks=tasks.active_count(),
        cache_enabled=cache.enabled,
        cache_hits=cache.hit_count(),
    )


def _process_task(
    task_id: str,
    question: str,
    top_k: int,
    cache: ValkeyCache,
) -> None:
    try:
        result = ask_with_sources(question, top_k=top_k)
        app.state.tasks.update(
            task_id,
            status="done",
            answer=result["answer"],
            sources=result["sources"],
        )
        cache.set(question, result)
    except Exception as e:
        app.state.tasks.update(
            task_id,
            status="error",
            error=str(e),
        )
