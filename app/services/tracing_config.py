from __future__ import annotations

import hashlib
from typing import Any

from agents import RunConfig, trace
from agents.tracing import custom_span

from app.models.schemas import ChatMessage

WORKFLOW_QUERY = "Clinical trial query"
WORKFLOW_AGENT = "Visualization agent"
TOOL_NAMESPACE = "ClinicalTrials.gov"


def build_trace_group_id(question: str, history: list[ChatMessage] | None = None) -> str:
    """Stable group id to link traces from the same conversation."""
    parts = [message.content for message in (history or [])]
    parts.append(question)
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"thread-{digest}"


def build_run_config(
    *,
    question: str,
    history: list[ChatMessage] | None = None,
    source: str = "api",
) -> RunConfig:
    preview = question.strip().replace("\n", " ")
    if len(preview) > 120:
        preview = f"{preview[:119]}…"

    metadata: dict[str, Any] = {
        "source": source,
        "question_preview": preview,
        "history_turns": len(history or []),
    }

    return RunConfig(
        workflow_name=WORKFLOW_AGENT,
        group_id=build_trace_group_id(question, history),
        trace_metadata=metadata,
    )


def query_trace(
    *,
    question: str,
    history: list[ChatMessage] | None = None,
    source: str = "api",
):
    """Top-level trace grouping agent run and post-processing."""
    preview = question.strip().replace("\n", " ")
    if len(preview) > 120:
        preview = f"{preview[:119]}…"

    return trace(
        workflow_name=WORKFLOW_QUERY,
        group_id=build_trace_group_id(question, history),
        metadata={
            "source": source,
            "question_preview": preview,
            "history_turns": len(history or []),
        },
    )


def postprocess_span(name: str, **data: Any):
    return custom_span(name, data or None)
