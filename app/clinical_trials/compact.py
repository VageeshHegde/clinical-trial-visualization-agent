from __future__ import annotations

from app.models.schemas import (
    AggregationResult,
    FilterOptionsResult,
    TrialSearchResult,
    TrialSummary,
)


def truncate_text(text: str | None, *, max_len: int) -> str | None:
    if text is None:
        return None
    cleaned = text.strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def compact_trial(
    trial: TrialSummary,
    *,
    max_title_chars: int,
    max_conditions: int,
) -> TrialSummary:
    conditions = trial.conditions[:max_conditions] if trial.conditions else []
    return trial.model_copy(
        update={
            "title": truncate_text(trial.title, max_len=max_title_chars) or trial.title,
            "conditions": conditions,
        }
    )


def compact_trials(
    trials: list[TrialSummary],
    *,
    max_trials: int,
    max_title_chars: int,
    max_conditions: int,
) -> list[TrialSummary]:
    limited = trials[:max_trials]
    return [
        compact_trial(
            trial,
            max_title_chars=max_title_chars,
            max_conditions=max_conditions,
        )
        for trial in limited
    ]


def compact_search_result(
    result: TrialSearchResult,
    *,
    max_trials: int,
    max_title_chars: int,
    max_conditions: int,
) -> TrialSearchResult:
    trials = compact_trials(
        result.trials,
        max_trials=max_trials,
        max_title_chars=max_title_chars,
        max_conditions=max_conditions,
    )
    return result.model_copy(
        update={
            "trials": trials,
            "total_returned": len(trials),
        }
    )


def compact_aggregation(result: AggregationResult) -> AggregationResult:
    """Drop optional traceability trials from tool output (not needed by the agent)."""
    if not result.trials:
        return result
    return result.model_copy(update={"trials": []})


def compact_filter_options(result: FilterOptionsResult) -> FilterOptionsResult:
    """Keep enum codes only; param mappings live in agent instructions."""
    return result.model_copy(
        update={
            "search_areas": {},
            "query_params": {},
            "notes": (
                "Enum codes for status/phase/study_type filters. "
                "Use query.cond, query.intr, filter.overallStatus, filter.advanced "
                "as documented in your instructions — avoid calling this tool again."
            ),
        }
    )
