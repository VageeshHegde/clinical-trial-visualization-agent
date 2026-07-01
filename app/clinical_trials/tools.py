from __future__ import annotations

from collections import Counter
from typing import Annotated, Literal

from agents import function_tool

from app.clinical_trials.client import ClinicalTrialsClient
from app.config import get_settings
from app.clinical_trials.extract import humanize_phase, humanize_status
from app.models.schemas import (
    AggregationBucket,
    AggregationResult,
    TrialSearchResult,
    TrialSummary,
)

_client: ClinicalTrialsClient | None = None


def _get_client() -> ClinicalTrialsClient:
    global _client
    if _client is None:
        _client = ClinicalTrialsClient(get_settings())
    return _client

GroupByField = Literal["status", "phase", "sponsor", "condition", "study_type"]


def _bucket_trials(trials: list[TrialSummary], group_by: GroupByField) -> list[AggregationBucket]:
    counter: Counter[str] = Counter()

    for trial in trials:
        if group_by == "status":
            key = humanize_status(trial.status or "UNKNOWN")
            counter[key] += 1
        elif group_by == "phase":
            phases = trial.phases or ["N/A"]
            for phase in phases:
                counter[humanize_phase(phase)] += 1
        elif group_by == "sponsor":
            counter[trial.sponsor or "Unknown sponsor"] += 1
        elif group_by == "condition":
            conditions = trial.conditions or ["Unspecified condition"]
            for condition in conditions:
                counter[condition] += 1
        elif group_by == "study_type":
            counter[trial.study_type or "UNKNOWN"] += 1

    return [
        AggregationBucket(label=label, count=count)
        for label, count in counter.most_common()
    ]


@function_tool
def search_clinical_trials(
    condition: Annotated[str | None, "Disease or condition, e.g. 'lung cancer' or 'diabetes'"] = None,
    intervention: Annotated[str | None, "Drug, device, or treatment name"] = None,
    sponsor: Annotated[str | None, "Sponsor or organization name"] = None,
    search_term: Annotated[str | None, "General full-text search across trial fields"] = None,
    status: Annotated[
        list[str] | None,
        "Overall status filters: RECRUITING, COMPLETED, ACTIVE_NOT_RECRUITING, etc.",
    ] = None,
    phase: Annotated[
        list[str] | None,
        "Phase filters: EARLY_PHASE1, PHASE1, PHASE2, PHASE3, PHASE4, NA",
    ] = None,
    page_size: Annotated[int, "Number of trials to return (1-200)"] = 50,
) -> TrialSearchResult:
    """Search ClinicalTrials.gov and return summarized trial records.

    Use only when the user wants to list individual trials. For counts or breakdowns
    by phase/status/sponsor, use count_trials_by_field instead.
    """
    trials, next_page_token = _get_client().search_studies(
        condition=condition,
        intervention=intervention,
        sponsor=sponsor,
        search_term=search_term,
        status=status,
        phase=phase,
        page_size=page_size,
    )
    return TrialSearchResult(
        total_returned=len(trials),
        has_more=next_page_token is not None,
        trials=trials,
        search_description=_get_client().describe_search(
            condition=condition,
            intervention=intervention,
            sponsor=sponsor,
            search_term=search_term,
            status=status,
            phase=phase,
        ),
    )


@function_tool
def get_clinical_trial(
    nct_id: Annotated[str, "ClinicalTrials.gov identifier, e.g. NCT01234567"],
) -> TrialSummary:
    """Fetch a single clinical trial by NCT ID."""
    return _get_client().get_study(nct_id.strip().upper())


@function_tool
def count_trials_by_field(
    group_by: Annotated[
        GroupByField,
        "Dimension to aggregate: status, phase, sponsor, condition, or study_type",
    ],
    condition: Annotated[str | None, "Disease or condition filter"] = None,
    intervention: Annotated[str | None, "Intervention filter"] = None,
    sponsor: Annotated[str | None, "Sponsor filter"] = None,
    search_term: Annotated[str | None, "General full-text search"] = None,
    status: Annotated[list[str] | None, "Status filters"] = None,
    phase: Annotated[list[str] | None, "Phase filters"] = None,
    page_size: Annotated[int, "Trials to sample for aggregation (1-200)"] = 100,
) -> AggregationResult:
    """Search trials and aggregate counts by field. Preferred for bar/pie charts.

    Returns buckets with label/count pairs suitable for chart_type bar or pie.
    """
    trials, _ = _get_client().search_studies(
        condition=condition,
        intervention=intervention,
        sponsor=sponsor,
        search_term=search_term,
        status=status,
        phase=phase,
        page_size=page_size,
    )
    buckets = _bucket_trials(trials, group_by)
    return AggregationResult(
        group_by=group_by,
        total_trials=len(trials),
        buckets=buckets,
        search_description=_get_client().describe_search(
            condition=condition,
            intervention=intervention,
            sponsor=sponsor,
            search_term=search_term,
            status=status,
            phase=phase,
        ),
    )
