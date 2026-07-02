from __future__ import annotations

import json
from collections import Counter
from typing import Annotated, Any, Literal

from agents import function_tool

from app.clinical_trials.client import ClinicalTrialsClient
from app.clinical_trials.extract import humanize_phase, humanize_status
from app.clinical_trials.filters import StudySearchFilters
from app.config import get_settings
from app.models.schemas import (
    AggregationBucket,
    AggregationResult,
    FilterOptionsResult,
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

_COUNT_TOOL_FILTER_KEYS = (
    "condition",
    "intervention",
    "sponsor",
    "lead_sponsor",
    "location",
    "search_term",
    "status",
    "phase",
    "study_type",
    "nct_ids",
    "agg_filters",
    "advanced_filter",
)


def sample_matching_trials(
    tool_args: dict[str, Any],
    *,
    page_size: int | None = None,
) -> list[TrialSummary]:
    """Fetch a small trial sample using the same filters as count_trials_by_field."""
    settings = get_settings()
    filter_kwargs = {key: tool_args.get(key) for key in _COUNT_TOOL_FILTER_KEYS}
    filters = _build_filters(**filter_kwargs)
    trials, _, _ = _get_client().search_studies(
        filters,
        page_size=settings.clamp_agent_trial_limit(page_size),
    )
    return trials


def _build_filters(
    *,
    condition: str | None = None,
    intervention: str | None = None,
    sponsor: str | None = None,
    lead_sponsor: str | None = None,
    location: str | None = None,
    search_term: str | None = None,
    status: list[str] | None = None,
    phase: list[str] | None = None,
    study_type: list[str] | None = None,
    nct_ids: list[str] | None = None,
    agg_filters: list[str] | None = None,
    advanced_filter: str | None = None,
    sort: str | None = None,
) -> StudySearchFilters:
    return StudySearchFilters(
        condition=condition,
        intervention=intervention,
        sponsor=sponsor,
        lead_sponsor=lead_sponsor,
        location=location,
        search_term=search_term,
        status=status,
        phase=phase,
        study_type=study_type,
        nct_ids=nct_ids,
        agg_filters=agg_filters,
        advanced_filter=advanced_filter,
        sort=sort,
    )


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
    condition: Annotated[str | None, "query.cond"] = None,
    intervention: Annotated[str | None, "query.intr"] = None,
    sponsor: Annotated[str | None, "query.spons"] = None,
    lead_sponsor: Annotated[str | None, "query.lead"] = None,
    location: Annotated[str | None, "query.locn"] = None,
    search_term: Annotated[str | None, "query.term"] = None,
    status: Annotated[list[str] | None, "filter.overallStatus"] = None,
    phase: Annotated[list[str] | None, "Phase enum codes"] = None,
    study_type: Annotated[list[str] | None, "StudyType enum codes"] = None,
    nct_ids: Annotated[list[str] | None, "filter.ids"] = None,
    agg_filters: Annotated[list[str] | None, "aggFilters"] = None,
    advanced_filter: Annotated[str | None, "filter.advanced Essie expression"] = None,
    sort: Annotated[str | None, "sort field"] = None,
    page_size: Annotated[
        int | None,
        "Optional pageSize; defaults to AGGREGATION_TOP_N from .env and is capped to that value",
    ] = None,
) -> TrialSearchResult:
    """List individual trials. Use count_trials_by_field for charts and breakdowns."""
    settings = get_settings()
    effective_page_size = settings.clamp_agent_trial_limit(page_size)
    filters = _build_filters(
        condition=condition,
        intervention=intervention,
        sponsor=sponsor,
        lead_sponsor=lead_sponsor,
        location=location,
        search_term=search_term,
        status=status,
        phase=phase,
        study_type=study_type,
        nct_ids=nct_ids,
        agg_filters=agg_filters,
        advanced_filter=advanced_filter,
        sort=sort,
    )
    client = _get_client()
    trials, next_page_token, total_count = client.search_studies(
        filters, page_size=effective_page_size
    )
    return TrialSearchResult(
        total_returned=len(trials),
        total_count=total_count,
        has_more=next_page_token is not None,
        trials=trials,
        search_description=client.describe_search(filters),
    )


@function_tool
def get_clinical_trial(
    nct_id: Annotated[str, "NCT ID, e.g. NCT01234567"],
) -> TrialSummary:
    """Fetch one trial by NCT ID."""
    return _get_client().get_study(nct_id.strip().upper())


@function_tool
def get_clinical_trial_filter_options() -> FilterOptionsResult:
    """Valid status/phase/study_type codes and query param names."""
    return FilterOptionsResult(**_get_client().get_filter_options())


@function_tool
def count_trials_by_field(
    group_by: Annotated[GroupByField, "status, phase, sponsor, condition, or study_type"],
    condition: Annotated[str | None, "query.cond"] = None,
    intervention: Annotated[str | None, "query.intr"] = None,
    sponsor: Annotated[str | None, "query.spons"] = None,
    lead_sponsor: Annotated[str | None, "query.lead"] = None,
    location: Annotated[str | None, "query.locn"] = None,
    search_term: Annotated[str | None, "query.term"] = None,
    status: Annotated[list[str] | None, "filter.overallStatus"] = None,
    phase: Annotated[list[str] | None, "Phase enum codes"] = None,
    study_type: Annotated[list[str] | None, "StudyType enum codes"] = None,
    nct_ids: Annotated[list[str] | None, "filter.ids"] = None,
    agg_filters: Annotated[list[str] | None, "aggFilters"] = None,
    advanced_filter: Annotated[str | None, "filter.advanced"] = None,
) -> AggregationResult:
    """Exact counts by field for charts. Large sponsor/condition lists are capped to top N."""
    filters = _build_filters(
        condition=condition,
        intervention=intervention,
        sponsor=sponsor,
        lead_sponsor=lead_sponsor,
        location=location,
        search_term=search_term,
        status=status,
        phase=phase,
        study_type=study_type,
        nct_ids=nct_ids,
        agg_filters=agg_filters,
        advanced_filter=advanced_filter,
    )
    client = _get_client()
    buckets, total_trials, data_source, buckets_capped, buckets_total = client.count_by_field(
        group_by,
        filters,
    )
    search_description = client.describe_search(filters)
    if buckets_capped:
        top_n = get_settings().aggregation_top_n
        cap_note = (
            f"; showing top {top_n} of {buckets_total} {group_by.replace('_', ' ')}s "
            f"(remainder grouped as Other to stay within model token limits)"
        )
        search_description = f"{search_description}{cap_note}"

    return AggregationResult(
        group_by=group_by,
        total_trials=total_trials,
        buckets=buckets,
        data_source=data_source,
        buckets_capped=buckets_capped,
        buckets_total=buckets_total if buckets_capped else None,
        search_description=f"{search_description}; aggregation={data_source}",
    )
