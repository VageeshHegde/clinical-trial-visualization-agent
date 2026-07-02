import argparse
import asyncio
import json
from pathlib import Path

from app.config import ensure_project_venv, get_settings
from app.models.schemas import ChatMessage, QueryRequest
from app.services.conversation import trim_history
from app.services.pipeline import answer_question

PROJECT_ROOT = Path(__file__).resolve().parent


def _bootstrap() -> None:
    settings = get_settings()
    settings.apply()


async def run_query(question: str) -> None:
    response = await answer_question(QueryRequest(question=question))
    print(json.dumps(response.model_dump(), indent=2))


async def run_repl() -> None:
    settings = get_settings()
    settings.require_openai_api_key()

    history: list[ChatMessage] = []
    print("Clinical Trial Visualization Agent (type 'exit' to quit)\n")

    while True:
        try:
            question = input("Question> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break

        trimmed = trim_history(history, max_messages=settings.chat_context_max_messages)
        response = await answer_question(
            QueryRequest(question=question, history=trimmed),
        )
        print(json.dumps(response.model_dump(), indent=2))
        history.append(ChatMessage(role="user", content=question))
        history.append(ChatMessage(role="assistant", content=response.visualization.summary))


def main() -> None:
    _bootstrap()

    parser = argparse.ArgumentParser(description="Clinical trial visualization agent")
    parser.add_argument("question", nargs="?", help="Question to ask about clinical trials")
    parser.add_argument(
        "--repl",
        action="store_true",
        help="Start an interactive question loop",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the FastAPI server (host/port from .env)",
    )
    args = parser.parse_args()

    settings = get_settings()

    if args.serve:
        import uvicorn

        uvicorn.run(
            "app.api:app",
            host=settings.api_host,
            port=settings.api_port,
            reload=settings.uvicorn_reload,
        )
        return

    if args.repl:
        asyncio.run(run_repl())
        return

    if args.question:
        asyncio.run(run_query(args.question))
        return

    parser.print_help()


if __name__ == "__main__":
    ensure_project_venv(PROJECT_ROOT)
    main()
