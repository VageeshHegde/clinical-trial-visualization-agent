from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.models.schemas import QueryRequest, QueryResponse
from app.routes.web import router as web_router
from app.services.pipeline import answer_question
from app.templating import STATIC_DIR


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.apply()
    yield


settings = get_settings()

app = FastAPI(
    title="Clinical Trial Visualization API",
    description=(
        "Ask questions about clinical trials in plain English and receive "
        "a structured visualization specification for frontend rendering."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(web_router)


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "openai_configured": bool(settings.openai_api_key),
    }


@app.post("/api/query", response_model=QueryResponse)
async def query_trials(request: QueryRequest) -> QueryResponse:
    try:
        return await answer_question(request)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
