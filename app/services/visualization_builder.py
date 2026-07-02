from __future__ import annotations

import re
from collections import Counter
from datetime import date

from app.config import get_settings
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
    (re.compile(r"\bnetwork(\s+graph)?\b|\brelationship(\s+map)?\b", re.I), ChartType.NETWORK),
    (
        re.compile(
            r"\btime\s*series\b|\bover\s+time\b|\btrend(s)?\b|\bby\s+year\b|\bper\s+year\b"
            r"|\bmonthly\b|\bannual(ly)?\b|\bstarted\s+(each|per)\b",
            re.I,
        ),
        ChartType.TIMESERIES,
    ),
    (re.compile(r"\bdonut(\s+chart)?\b|\bdoughnut(\s+chart)?\b", re.I), ChartType.DONUT),
    (re.compile(r"\bpie(\s+chart)?\b", re.I), ChartType.PIE),
    (re.compile(r"\bbar(\s+chart)?\b", re.I), ChartType.BAR),
    (re.compile(r"\bline(\s+chart)?\b", re.I), ChartType.LINE),
]

_NETWORK_PATTERNS = [
    re.compile(r"\bnetwork(\s+graph)?\b", re.I),
    re.compile(r"\brelationship(\s+map)?\b", re.I),
    re.compile(r"\bconnections?\s+between\b", re.I),
    re.compile(r"\bgraph\s+of\b", re.I),
    re.compile(r"\blink(s|ed)?\s+between\b", re.I),
    re.compile(r"\bsponsors?\s+and\s+conditions?\b", re.I),
]

_TIMESERIES_PATTERNS = [
    re.compile(r"\btime\s*series\b", re.I),
    re.compile(r"\bover\s+time\b", re.I),
    re.compile(r"\btrend(s)?\b", re.I),
    re.compile(r"\bby\s+year\b", re.I),
    re.compile(r"\bper\s+year\b", re.I),
    re.compile(r"\bmonthly\b", re.I),
    re.compile(r"\bannual(ly)?\b", re.I),
    re.compile(r"\bstarted\s+(each|per)\b", re.I),
    re.compile(r"\btrials\s+started\b", re.I),
    re.compile(r"\bwhen\s+(were|was)\b.*\bstarted\b", re.I),
]


def _asks_for_list(question: str) -> bool:
    return any(pattern.search(question) for pattern in _LIST_PATTERNS)


def _asks_for_network(question: str) -> bool:
    return any(pattern.search(question) for pattern in _NETWORK_PATTERNS)


def _asks_for_timeseries(question: str) -> bool:
    return any(pattern.search(question) for pattern in _TIMESERIES_PATTERNS)


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
    pie_max = get_settings().chart_pie_max_buckets
    if bucket_count <= pie_max:
        return ChartType.PIE
    return ChartType.BAR


def _parse_start_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    match = re.match(r"^(\d{4})-(\d{2})(?:-(\d{2}))?$", text)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3) or 1)
        try:
            return date(year, month, day)
        except ValueError:
            return None
    match = re.match(r"^(\d{4})$", text)
    if match:
        return date(int(match.group(1)), 1, 1)
    return None


def _timeseries_granularity(question: str, dates: list[date]) -> str:
    if re.search(r"\b(monthly|per month|each month|by month)\b", question, re.I):
        return "month"
    if re.search(r"\b(yearly|per year|each year|by year|annual(ly)?)\b", question, re.I):
        return "year"
    if len(dates) < 2:
        return "year"
    span_days = (max(dates) - min(dates)).days
    return "year" if span_days > 730 else "month"


def _timeseries_bucket_key(parsed: date, granularity: str) -> str:
    if granularity == "year":
        return f"{parsed.year}-01-01"
    return f"{parsed.year}-{parsed.month:02d}-01"


def build_timeseries_from_trials(
    question: str,
    trials: list[TrialSummary],
    *,
    title: str,
    summary: str,
    meta: dict,
) -> VisualizationSpec:
    """Count trials by start date bucket (year or month)."""
    parsed_dates = [
        parsed
        for trial in trials
        if (parsed := _parse_start_date(trial.start_date)) is not None
    ]
    granularity = _timeseries_granularity(question, parsed_dates)
    counts: Counter[str] = Counter()

    for trial in trials:
        parsed = _parse_start_date(trial.start_date)
        if parsed is None:
            continue
        counts[_timeseries_bucket_key(parsed, granularity)] += 1

    data = [
        {"date": bucket, "count": count}
        for bucket, count in sorted(counts.items())
        if count > 0
    ]
    x_label = "Start year" if granularity == "year" else "Start month"

    return VisualizationSpec(
        chart_type=ChartType.TIMESERIES,
        title=title,
        summary=summary,
        data=data,
        encoding=ChartEncoding(x="date", y="count"),
        x_axis=AxisEncoding(field="date", label=x_label),
        y_axis=AxisEncoding(field="count", label="Number of trials"),
        meta={
            **meta,
            "timeseries_granularity": granularity,
            "trial_count": len(trials),
            "dated_trials": len(parsed_dates),
            "chart_source": "trial_timeseries",
        },
    )


def build_network_from_trials(
    trials: list[TrialSummary],
    *,
    title: str,
    summary: str,
    meta: dict,
) -> VisualizationSpec:
    """Bipartite sponsor ↔ condition graph from trial rows."""
    nodes: dict[str, dict[str, str]] = {}
    link_counts: Counter[tuple[str, str]] = Counter()

    def ensure_node(group: str, label: str) -> str:
        node_key = f"{group}:{label}"
        if node_key not in nodes:
            nodes[node_key] = {"id": node_key, "label": label, "group": group}
        return node_key

    for trial in trials:
        sponsor_id = ensure_node("sponsor", trial.sponsor or "Unknown sponsor")
        conditions = trial.conditions or ["Unspecified condition"]
        for condition in conditions:
            condition_id = ensure_node("condition", condition)
            link_counts[(sponsor_id, condition_id)] += 1

    links = [
        {"source": source, "target": target, "value": count}
        for (source, target), count in link_counts.items()
        if count > 0
    ]

    return VisualizationSpec(
        chart_type=ChartType.NETWORK,
        title=title,
        summary=summary,
        data=[{"nodes": list(nodes.values()), "links": links}],
        encoding=ChartEncoding(label="label", color="group"),
        meta={
            **meta,
            "network_type": "sponsor_condition",
            "trial_count": len(trials),
            "chart_source": "trial_network",
        },
    )


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
    if visualization.chart_type == ChartType.NETWORK:
        return visualization
    if visualization.chart_type == ChartType.TIMESERIES:
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
    *,
    trials: list[TrialSummary] | None = None,
) -> VisualizationSpec:
    trial_rows = list(trials or [])

    if _asks_for_network(question) and trial_rows:
        return build_network_from_trials(
            trial_rows,
            title=visualization.title,
            summary=visualization.summary,
            meta=visualization.meta,
        )

    if _asks_for_timeseries(question) and trial_rows:
        return build_timeseries_from_trials(
            question,
            trial_rows,
            title=visualization.title,
            summary=visualization.summary,
            meta=visualization.meta,
        )

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
