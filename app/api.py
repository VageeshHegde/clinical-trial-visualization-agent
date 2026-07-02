from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.errors import TOKEN_RATE_LIMIT_MESSAGE, is_token_rate_limit_error
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


@app.post(
    "/api/query",
    response_model=QueryResponse,
    responses={
        422: {"description": "Validation error (invalid or off-topic question)"},
        429: {"description": "OpenAI token rate limit exceeded (TPM)"},
        503: {"description": "Service unavailable (e.g. missing OPENAI_API_KEY)"},
        500: {"description": "Internal server error"},
    },
)
async def query_trials(request: QueryRequest) -> QueryResponse:
    try:
        return await answer_question(request)
    except ValueError as exc:
        status_code = 429 if str(exc) == TOKEN_RATE_LIMIT_MESSAGE else 503
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        if is_token_rate_limit_error(exc):
            raise HTTPException(status_code=429, detail=TOKEN_RATE_LIMIT_MESSAGE) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
