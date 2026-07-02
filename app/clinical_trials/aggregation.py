from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from app.clinical_trials.extract import humanize_phase, humanize_status
from app.clinical_trials.filters import StudySearchFilters
from app.models.schemas import AggregationBucket

GROUP_BY_STATS_FIELD: dict[str, tuple[str, str]] = {
    "status": ("OverallStatus", "ENUM"),
    "phase": ("Phase", "ENUM"),
    "study_type": ("StudyType", "ENUM"),
    "sponsor": ("LeadSponsorName", "STRING"),
    "condition": ("Condition", "STRING"),
}

GROUP_BY_SCAN_FIELD: dict[str, str] = {
    "status": "protocolSection.statusModule.overallStatus",
    "phase": "protocolSection.designModule.phases",
    "study_type": "protocolSection.designModule.studyType",
    "sponsor": "protocolSection.sponsorCollaboratorsModule.leadSponsor.name",
    "condition": "protocolSection.conditionsModule.conditions",
}

_LABELERS: dict[str, Callable[[str], str]] = {
    "status": humanize_status,
    "phase": humanize_phase,
    "study_type": lambda value: value.replace("_", " ").title(),
    "sponsor": lambda value: value,
    "condition": lambda value: value,
}

SCAN_PAGE_SIZE = 1000

HIGH_CARDINALITY_GROUP_FIELDS = frozenset({"sponsor", "condition"})


def cap_buckets(
    buckets: list[AggregationBucket],
    *,
    top_n: int,
    group_by: str,
) -> tuple[list[AggregationBucket], bool, int]:
    """Keep top-N buckets and roll the remainder into an Other category."""
    total_buckets = len(buckets)
    if total_buckets <= top_n:
        return buckets, False, total_buckets

    kept = buckets[:top_n]
    remainder = buckets[top_n:]
    other_count = sum(bucket.count for bucket in remainder)
    dimension = group_by.replace("_", " ")
    kept.append(
        AggregationBucket(
            label=f"Other ({len(remainder)} {dimension}s)",
            count=other_count,
        )
    )
    return kept, True, total_buckets


def has_search_filters(filters: StudySearchFilters) -> bool:
    return filters.active()


def label_group_value(
    group_by: str,
    raw_value: str,
    *,
    label_for: Callable[[str, str], str] | None = None,
) -> str:
    if label_for is not None and group_by in {"status", "phase", "study_type"}:
        from app.clinical_trials.metadata import GROUP_BY_ENUM_PIECE

        piece = GROUP_BY_ENUM_PIECE[group_by]
        return label_for(piece, raw_value)

    labeler = _LABELERS.get(group_by, lambda value: value)
    return labeler(raw_value)


def buckets_from_counter(
    group_by: str,
    counter: Counter[str],
    *,
    label_for: Callable[[str, str], str] | None = None,
) -> list[AggregationBucket]:
    return [
        AggregationBucket(
            label=label_group_value(group_by, label, label_for=label_for),
            count=count,
        )
        for label, count in counter.most_common()
        if count > 0
    ]


def extract_group_values(study: dict[str, Any], group_by: str) -> list[str]:
    protocol = study.get("protocolSection", {})

    if group_by == "status":
        value = (protocol.get("statusModule") or {}).get("overallStatus")
        return [value or "UNKNOWN"]

    if group_by == "phase":
        phases = (protocol.get("designModule") or {}).get("phases") or []
        return phases or ["NA"]

    if group_by == "study_type":
        value = (protocol.get("designModule") or {}).get("studyType")
        return [value or "UNKNOWN"]

    if group_by == "sponsor":
        value = ((protocol.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}).get(
            "name"
        )
        return [value or "Unknown sponsor"]

    if group_by == "condition":
        conditions = (protocol.get("conditionsModule") or {}).get("conditions") or []
        return conditions or ["Unspecified condition"]

    return []


def dimension_filter_params(group_by: str, raw_value: str) -> dict[str, str]:
    if group_by == "status":
        return {"filter.overallStatus": raw_value}

    if group_by == "phase":
        if raw_value in {"PHASE1", "PHASE2", "PHASE3", "PHASE4"}:
            return {"aggFilters": f"phase:{raw_value[-1]}"}
        return {"filter.advanced": f"AREA[Phase]{raw_value}"}

    if group_by == "study_type":
        return {"filter.advanced": f"AREA[StudyType]{raw_value}"}

    raise ValueError(f"Unsupported enum dimension: {group_by}")


def filters_without_dimension(group_by: str, filters: StudySearchFilters) -> StudySearchFilters:
    return filters.without_dimension(group_by)
