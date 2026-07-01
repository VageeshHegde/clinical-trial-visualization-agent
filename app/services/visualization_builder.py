from __future__ import annotations

import re

from app.clinical_trials.tools import GroupByField, _bucket_trials
from app.models.schemas import (
    AggregationResult,
    AxisEncoding,
    ChartEncoding,
    ChartType,
    TrialSearchResult,
    TrialSummary,
    VisualizationSpec,
)

_GROUP_BY_PATTERNS: list[tuple[re.Pattern[str], GroupByField]] = [
    (re.compile(r"\bby\s+phase", re.I), "phase"),
    (re.compile(r"\bphase\s+breakdown", re.I), "phase"),
    (re.compile(r"\bby\s+status", re.I), "status"),
    (re.compile(r"\bstatus\s+breakdown", re.I), "status"),
    (re.compile(r"\bby\s+sponsor", re.I), "sponsor"),
    (re.compile(r"\bby\s+condition", re.I), "condition"),
    (re.compile(r"\bby\s+study\s+type", re.I), "study_type"),
]

_BREAKDOWN_PATTERNS = [
    re.compile(r"\bhow\s+many\b", re.I),
    re.compile(r"\bbreak\s*down\b", re.I),
    re.compile(r"\bdistribution\b", re.I),
    re.compile(r"\bcompare\b", re.I),
    re.compile(r"\bby\s+\w+", re.I),
    re.compile(r"\bcount\b", re.I),
]

_LIST_PATTERNS = [
    re.compile(r"\blist\b", re.I),
    re.compile(r"\bshow\s+trials\b", re.I),
    re.compile(r"\btable\b", re.I),
    re.compile(r"\bnct\b", re.I),
    re.compile(r"\bdetails?\b", re.I),
]


def _asks_for_list(question: str) -> bool:
    return any(pattern.search(question) for pattern in _LIST_PATTERNS)


def _asks_for_breakdown(question: str) -> bool:
    return any(pattern.search(question) for pattern in _BREAKDOWN_PATTERNS)


def _infer_group_by(question: str) -> GroupByField | None:
    for pattern, group_by in _GROUP_BY_PATTERNS:
        if pattern.search(question):
            return group_by
    if _asks_for_breakdown(question):
        return "phase"
    return None


def _group_by_label(group_by: GroupByField) -> str:
    return group_by.replace("_", " ").title()


def _choose_chart_type(bucket_count: int) -> ChartType:
    if bucket_count <= 6:
        return ChartType.PIE
    return ChartType.BAR


def build_chart_from_buckets(
    group_by: GroupByField,
    buckets: list[tuple[str, int]],
    *,
    title: str,
    summary: str,
    meta: dict,
    total_trials: int,
) -> VisualizationSpec:
    data = [{"label": label, "count": count} for label, count in buckets if count > 0]
    chart_type = _choose_chart_type(len(data))
    group_label = _group_by_label(group_by)

    return VisualizationSpec(
        chart_type=chart_type,
        title=title,
        summary=summary,
        data=data,
        encoding=ChartEncoding(x="label", y="count"),
        x_axis=AxisEncoding(field="label", label=group_label),
        y_axis=AxisEncoding(field="count", label="Number of trials"),
        meta={
            **meta,
            "group_by": group_by,
            "total_trials": total_trials,
            "chart_source": "aggregation",
        },
    )


def build_chart_from_aggregation(
    aggregation: AggregationResult,
    visualization: VisualizationSpec,
) -> VisualizationSpec:
    buckets = [(bucket.label, bucket.count) for bucket in aggregation.buckets]
    return build_chart_from_buckets(
        aggregation.group_by,  # type: ignore[arg-type]
        buckets,
        title=visualization.title,
        summary=visualization.summary,
        meta=visualization.meta,
        total_trials=aggregation.total_trials,
    )


def _collect_tool_outputs(result: object) -> list[object]:
    outputs: list[object] = []
    new_items = getattr(result, "new_items", None)
    if not new_items:
        return outputs

    for item in new_items:
        if getattr(item, "type", None) != "tool_call_output_item":
            continue
        output = getattr(item, "output", None)
        if output is not None:
            outputs.append(output)
    return outputs


def _is_trial_row_table(visualization: VisualizationSpec) -> bool:
    if visualization.chart_type != ChartType.TABLE or not visualization.data:
        return False
    first_row = visualization.data[0]
    return "nct_id" in first_row or "title" in first_row


def enhance_visualization(
    question: str,
    result: object,
    visualization: VisualizationSpec,
) -> VisualizationSpec:
    if _asks_for_list(question):
        return visualization

    for output in _collect_tool_outputs(result):
        if isinstance(output, AggregationResult) and output.buckets:
            return build_chart_from_aggregation(output, visualization)

    if not _asks_for_breakdown(question):
        return visualization

    group_by = _infer_group_by(question)
    if group_by is None:
        return visualization

    if visualization.chart_type != ChartType.TABLE and not _is_trial_row_table(visualization):
        return visualization

    trials: list[TrialSummary] = []
    for output in _collect_tool_outputs(result):
        if isinstance(output, TrialSearchResult):
            trials.extend(output.trials)
        elif isinstance(output, TrialSummary):
            trials.append(output)

    if not trials:
        return visualization

    buckets = _bucket_trials(trials, group_by)
    bucket_pairs = [(bucket.label, bucket.count) for bucket in buckets]
    return build_chart_from_buckets(
        group_by,
        bucket_pairs,
        title=visualization.title,
        summary=visualization.summary,
        meta=visualization.meta,
        total_trials=len(trials),
    )
