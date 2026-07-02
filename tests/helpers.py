from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.schemas import AggregationBucket, AggregationResult, TrialSummary, VisualizationSpec


@dataclass
class MockToolOutputItem:
    type: str = "tool_call_output_item"
    output: Any = None


@dataclass
class MockRunResult:
    new_items: list[MockToolOutputItem]


def make_aggregation_result(
    *,
    group_by: str = "phase",
    buckets: list[tuple[str, int]] | None = None,
    total_trials: int | None = None,
) -> AggregationResult:
    if buckets is None:
        buckets = [
            ("Phase 1", 12),
            ("Phase 2", 34),
            ("Phase 3", 28),
            ("Phase 4", 9),
            ("Not Applicable", 5),
            ("Early Phase 1", 3),
            ("Unknown", 2),
        ]
    bucket_models = [AggregationBucket(label=label, count=count) for label, count in buckets]
    computed_total = sum(count for _, count in buckets)
    return AggregationResult(
        group_by=group_by,
        total_trials=total_trials if total_trials is not None else computed_total,
        buckets=bucket_models,
        search_description="condition='diabetes'",
        data_source="stats_api",
    )


def make_small_aggregation_result() -> AggregationResult:
    return make_aggregation_result(
        buckets=[
            ("Phase 1", 4),
            ("Phase 2", 11),
            ("Phase 3", 7),
            ("Not Applicable", 2),
        ],
        total_trials=24,
    )


def make_sample_trials() -> list[TrialSummary]:
    return [
        TrialSummary(
            nct_id="NCT00000001",
            title="Diabetes Study A",
            status="RECRUITING",
            phases=["PHASE2"],
            conditions=["Type 2 Diabetes"],
            sponsor="Acme Pharma",
            start_date="2020-03-15",
        ),
        TrialSummary(
            nct_id="NCT00000002",
            title="Diabetes Study B",
            status="RECRUITING",
            phases=["PHASE3"],
            conditions=["Type 1 Diabetes"],
            sponsor="Beta Research",
            start_date="2021-07-01",
        ),
        TrialSummary(
            nct_id="NCT00000003",
            title="Diabetes Study C",
            status="COMPLETED",
            phases=["PHASE2"],
            conditions=["Type 2 Diabetes"],
            sponsor="Acme Pharma",
            start_date="2019-01-10",
        ),
    ]


def make_base_visualization(**overrides: Any) -> VisualizationSpec:
    defaults = {
        "chart_type": "table",
        "title": "Clinical trial results",
        "summary": "Sample summary for evaluation.",
        "data": [{"nct_id": "NCT00000001", "title": "Example"}],
        "meta": {"search_description": "condition='diabetes'"},
    }
    defaults.update(overrides)
    return VisualizationSpec.model_validate(defaults)


def make_run_with_aggregation(aggregation: AggregationResult) -> MockRunResult:
    return MockRunResult(new_items=[MockToolOutputItem(output=aggregation)])
