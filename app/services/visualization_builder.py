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
    (re.compile(r"\bwhich\s+sponsors?\b", re.I), "sponsor"),
    (re.compile(r"\bmost\s+sponsors?\b", re.I), "sponsor"),
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
    re.compile(r"\bwhich\s+sponsors?\b", re.I),
    re.compile(r"\bmost\s+sponsors?\b", re.I),
]

_LIST_PATTERNS = [
    re.compile(r"\blist\b", re.I),
    re.compile(r"\bshow\s+trials\b", re.I),
    re.compile(r"\btable\b", re.I),
    re.compile(r"\bnct\b", re.I),
    re.compile(r"\bdetails?\b", re.I),
]

_CHART_TYPE_PATTERNS: list[tuple[re.Pattern[str], ChartType]] = [
    (re.compile(r"\bdonut(\s+chart)?\b|\bdoughnut(\s+chart)?\b", re.I), ChartType.DONUT),
    (re.compile(r"\bpie(\s+chart)?\b", re.I), ChartType.PIE),
    (re.compile(r"\bbar(\s+chart)?\b", re.I), ChartType.BAR),
    (re.compile(r"\bline(\s+chart)?\b", re.I), ChartType.LINE),
]


def _asks_for_list(question: str) -> bool:
    return any(pattern.search(question) for pattern in _LIST_PATTERNS)


def _preferred_chart_type(question: str) -> ChartType | None:
    for pattern, chart_type in _CHART_TYPE_PATTERNS:
        if pattern.search(question):
            return chart_type
    return None


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
    preferred_chart_type: ChartType | None = None,
) -> VisualizationSpec:
    data = [{"label": label, "count": count} for label, count in buckets if count > 0]
    chart_type = preferred_chart_type or _choose_chart_type(len(data))
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
    *,
    preferred_chart_type: ChartType | None = None,
) -> VisualizationSpec:
    buckets = [(bucket.label, bucket.count) for bucket in aggregation.buckets]
    meta = {
        **visualization.meta,
        "aggregation_source": aggregation.data_source,
    }
    if aggregation.buckets_capped:
        meta["buckets_capped"] = True
        meta["buckets_total"] = aggregation.buckets_total
    chart_type = preferred_chart_type
    if chart_type is None and visualization.chart_type in {ChartType.PIE, ChartType.DONUT}:
        chart_type = visualization.chart_type
    return build_chart_from_buckets(
        aggregation.group_by,  # type: ignore[arg-type]
        buckets,
        title=visualization.title,
        summary=visualization.summary,
        meta=meta,
        total_trials=aggregation.total_trials,
        preferred_chart_type=chart_type,
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


def _is_label_count_chart(visualization: VisualizationSpec) -> bool:
    if not visualization.data:
        return False
    first_row = visualization.data[0]
    return "label" in first_row and "count" in first_row


def _as_aggregation_result(output: object) -> AggregationResult | None:
    if isinstance(output, AggregationResult):
        return output
    if isinstance(output, dict):
        try:
            return AggregationResult.model_validate(output)
        except Exception:
            return None
    return None


def _apply_preferred_chart_type(
    question: str,
    visualization: VisualizationSpec,
) -> VisualizationSpec:
    preferred = _preferred_chart_type(question)
    if not preferred or _asks_for_list(question):
        return visualization
    if visualization.chart_type == preferred:
        return visualization
    if _is_label_count_chart(visualization) or visualization.chart_type in {
        ChartType.BAR,
        ChartType.PIE,
        ChartType.DONUT,
    }:
        return visualization.model_copy(update={"chart_type": preferred})
    return visualization


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

    preferred = _preferred_chart_type(question)

    for output in _collect_tool_outputs(result):
        aggregation = _as_aggregation_result(output)
        if aggregation and aggregation.buckets:
            rebuilt = build_chart_from_aggregation(
                aggregation,
                visualization,
                preferred_chart_type=preferred,
            )
            return _apply_preferred_chart_type(question, rebuilt)

    if not _asks_for_breakdown(question):
        return _apply_preferred_chart_type(question, visualization)

    group_by = _infer_group_by(question)
    if group_by is None:
        return _apply_preferred_chart_type(question, visualization)

    if visualization.chart_type != ChartType.TABLE and not _is_trial_row_table(visualization):
        return _apply_preferred_chart_type(question, visualization)

    trials: list[TrialSummary] = []
    for output in _collect_tool_outputs(result):
        if isinstance(output, TrialSearchResult):
            trials.extend(output.trials)
        elif isinstance(output, TrialSummary):
            trials.append(output)

    if not trials:
        return _apply_preferred_chart_type(question, visualization)

    buckets = _bucket_trials(trials, group_by)
    bucket_pairs = [(bucket.label, bucket.count) for bucket in buckets]
    rebuilt = build_chart_from_buckets(
        group_by,
        bucket_pairs,
        title=visualization.title,
        summary=visualization.summary,
        meta=visualization.meta,
        total_trials=len(trials),
        preferred_chart_type=preferred,
    )
    return _apply_preferred_chart_type(question, rebuilt)
