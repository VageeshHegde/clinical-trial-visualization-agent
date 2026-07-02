from __future__ import annotations

from app.models.schemas import ChatMessage
from app.services.tracing_config import (
    WORKFLOW_AGENT,
    WORKFLOW_QUERY,
    build_run_config,
    build_trace_group_id,
)


def test_trace_group_id_is_stable() -> None:
    history = [ChatMessage(role="user", content="How many diabetes trials?")]
    first = build_trace_group_id("Break down by phase", history)
    second = build_trace_group_id("Break down by phase", history)
    assert first == second
    assert first.startswith("thread-")


def test_run_config_names() -> None:
    config = build_run_config(question="How many trials?", source="cli")
    assert config.workflow_name == WORKFLOW_AGENT
    assert config.group_id is not None
    assert config.trace_metadata is not None
    assert config.trace_metadata["source"] == "cli"


def test_workflow_names_are_distinct() -> None:
    assert WORKFLOW_QUERY != WORKFLOW_AGENT
