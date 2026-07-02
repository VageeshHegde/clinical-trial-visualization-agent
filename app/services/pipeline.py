from __future__ import annotations

import json

from agents import Runner

from app.agent.visualization import create_visualization_agent
from app.clinical_trials.tools import sample_matching_trials
from app.config import get_settings
from app.errors import TOKEN_RATE_LIMIT_MESSAGE, is_token_rate_limit_error
from app.models.schemas import (
    AgentVisualizationOutput,
    AggregationResult,
    QueryRequest,
    QueryResponse,
    TrialSearchResult,
    TrialSummary,
)
from app.services.conversation import build_agent_input, contextual_question, trim_history
from app.services.visualization_builder import enhance_visualization


async def answer_question(request: QueryRequest) -> QueryResponse:
    settings = get_settings()
    settings.apply()
    settings.require_openai_api_key()

    history = trim_history(request.history, max_messages=settings.chat_context_max_messages)
    agent_input = build_agent_input(
        request.question,
        history,
        max_messages=settings.chat_context_max_messages,
    )
    question_context = contextual_question(request.question, history)

    agent = create_visualization_agent(settings)
    try:
        result = await Runner.run(agent, agent_input)
    except Exception as exc:
        if is_token_rate_limit_error(exc):
            raise ValueError(TOKEN_RATE_LIMIT_MESSAGE) from exc
        raise

    agent_output = result.final_output
    if not isinstance(agent_output, AgentVisualizationOutput):
        raise TypeError("Agent did not return an AgentVisualizationOutput")

    trials = _extract_trials_from_run(
        result, sample_size=settings.clamp_agent_trial_limit()
    )

    visualization = enhance_visualization(
        question_context,
        result,
        agent_output.visualization,
        trials=trials,
    )

    return QueryResponse(
        question=request.question,
        visualization=visualization,
        follow_questions=agent_output.follow_questions,
        trials=trials,
    )


def _extract_trials_from_run(result: object, *, sample_size: int) -> list[TrialSummary]:
    """Collect trial summaries from tool outputs, with aggregation fallbacks."""
    trials: list[TrialSummary] = []
    new_items = getattr(result, "new_items", None)
    if not new_items:
        return trials

    for item in new_items:
        if getattr(item, "type", None) != "tool_call_output_item":
            continue
        output = getattr(item, "output", None)
        if output is None:
            continue
        _collect_trials(output, trials)

    unique = _dedupe_trials(trials, sample_size)
    if unique:
        return unique

    return _sample_trials_from_aggregation(result, sample_size=sample_size)


def _sample_trials_from_aggregation(result: object, *, sample_size: int) -> list[TrialSummary]:
    """When charts use count_trials_by_field, fetch a small matching trial sample."""
    new_items = getattr(result, "new_items", None)
    if not new_items:
        return []

    last_args: dict[str, object] | None = None
    for item in new_items:
        if getattr(item, "type", None) != "tool_call_output_item":
            continue

        aggregation = _as_aggregation_result(getattr(item, "output", None))
        if aggregation is None or aggregation.total_trials <= 0:
            continue

        call_id = getattr(item, "call_id", None)
        if not call_id:
            continue

        args = _find_tool_call_args(new_items, call_id, "count_trials_by_field")
        if args is not None:
            last_args = args

    if last_args is None:
        return []

    sampled = sample_matching_trials(last_args, page_size=sample_size)
    return _dedupe_trials(sampled, sample_size)


def _find_tool_call_args(
    new_items: object,
    call_id: str,
    tool_name: str,
) -> dict[str, object] | None:
    for item in new_items:
        if getattr(item, "type", None) != "tool_call_item":
            continue
        if getattr(item, "call_id", None) != call_id:
            continue
        if getattr(item, "tool_name", None) != tool_name:
            continue

        raw_item = getattr(item, "raw_item", None)
        arguments = getattr(raw_item, "arguments", None)
        if arguments is None and isinstance(raw_item, dict):
            arguments = raw_item.get("arguments")
        if not arguments:
            return {}

        parsed = json.loads(arguments)
        return parsed if isinstance(parsed, dict) else None
    return None


def _dedupe_trials(trials: list[TrialSummary], limit: int) -> list[TrialSummary]:
    seen: set[str] = set()
    unique: list[TrialSummary] = []
    for trial in trials:
        if trial.nct_id in seen:
            continue
        seen.add(trial.nct_id)
        unique.append(trial)
    return unique[:limit]


def _as_aggregation_result(output: object) -> AggregationResult | None:
    if isinstance(output, AggregationResult):
        return output
    if isinstance(output, dict):
        try:
            return AggregationResult.model_validate(output)
        except Exception:
            return None
    return None


def _collect_trials(output: object, trials: list[TrialSummary]) -> None:
    if isinstance(output, TrialSummary):
        trials.append(output)
        return

    search_result = _as_trial_search_result(output)
    if search_result is not None:
        trials.extend(search_result.trials)
        return

    aggregation = _as_aggregation_result(output)
    if aggregation is not None:
        trials.extend(aggregation.trials)
        return

    trials_attr = getattr(output, "trials", None)
    if isinstance(trials_attr, list):
        for trial in trials_attr:
            parsed = _as_trial_summary(trial)
            if parsed is not None:
                trials.append(parsed)
        return

    if isinstance(output, dict) and isinstance(output.get("trials"), list):
        for trial in output["trials"]:
            parsed = _as_trial_summary(trial)
            if parsed is not None:
                trials.append(parsed)


def _as_trial_search_result(output: object) -> TrialSearchResult | None:
    if isinstance(output, TrialSearchResult):
        return output
    if isinstance(output, dict):
        try:
            return TrialSearchResult.model_validate(output)
        except Exception:
            return None
    return None


def _as_trial_summary(value: object) -> TrialSummary | None:
    if isinstance(value, TrialSummary):
        return value
    if isinstance(value, dict):
        try:
            return TrialSummary.model_validate(value)
        except Exception:
            return None
    return None
