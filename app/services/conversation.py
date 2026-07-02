from __future__ import annotations

from typing import Literal

from openai.types.responses import ResponseInputItemParam

from app.models.schemas import ChatMessage

ChatRole = Literal["user", "assistant"]


def trim_history(history: list[ChatMessage], *, max_messages: int) -> list[ChatMessage]:
    if max_messages <= 0 or not history:
        return []
    return history[-max_messages:]


def build_agent_input(
    question: str,
    history: list[ChatMessage],
    *,
    max_messages: int,
) -> str | list[ResponseInputItemParam]:
    prior = trim_history(history, max_messages=max_messages)
    if not prior:
        return question

    items: list[ResponseInputItemParam] = [
        {"role": message.role, "content": message.content} for message in prior
    ]
    items.append({"role": "user", "content": question})
    return items


def contextual_question(question: str, history: list[ChatMessage], *, max_user_turns: int = 3) -> str:
    """Combine recent user turns for post-processing heuristics (chart type, filters)."""
    user_turns = [message.content for message in history if message.role == "user"]
    if not user_turns:
        return question
    combined = user_turns[-max_user_turns:] + [question]
    return "\n".join(combined)
