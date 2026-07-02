from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class StudySearchFilters:
    """ClinicalTrials.gov /studies query filters used across search and aggregation."""

    condition: str | None = None
    intervention: str | None = None
    sponsor: str | None = None
    lead_sponsor: str | None = None
    location: str | None = None
    search_term: str | None = None
    status: list[str] | None = None
    phase: list[str] | None = None
    study_type: list[str] | None = None
    nct_ids: list[str] | None = None
    agg_filters: list[str] | None = None
    advanced_filter: str | None = None
    sort: str | None = None

    def active(self) -> bool:
        return any(
            [
                self.condition,
                self.intervention,
                self.sponsor,
                self.lead_sponsor,
                self.location,
                self.search_term,
                self.status,
                self.phase,
                self.study_type,
                self.nct_ids,
                self.agg_filters,
                self.advanced_filter,
            ]
        )

    def without_dimension(self, group_by: str) -> StudySearchFilters:
        if group_by == "status":
            return replace(self, status=None)
        if group_by == "phase":
            return replace(self, phase=None)
        if group_by == "study_type":
            return replace(self, study_type=None)
        return self

    def describe(self) -> str:
        parts: list[str] = []
        if self.condition:
            parts.append(f"condition={self.condition!r}")
        if self.intervention:
            parts.append(f"intervention={self.intervention!r}")
        if self.sponsor:
            parts.append(f"sponsor={self.sponsor!r}")
        if self.lead_sponsor:
            parts.append(f"lead_sponsor={self.lead_sponsor!r}")
        if self.location:
            parts.append(f"location={self.location!r}")
        if self.search_term:
            parts.append(f"term={self.search_term!r}")
        if self.status:
            parts.append(f"status={', '.join(self.status)}")
        if self.phase:
            parts.append(f"phase={', '.join(self.phase)}")
        if self.study_type:
            parts.append(f"study_type={', '.join(self.study_type)}")
        if self.nct_ids:
            parts.append(f"nct_ids={', '.join(self.nct_ids)}")
        if self.agg_filters:
            parts.append(f"agg_filters={', '.join(self.agg_filters)}")
        if self.advanced_filter:
            parts.append(f"advanced_filter={self.advanced_filter!r}")
        if self.sort:
            parts.append(f"sort={self.sort!r}")
        return "; ".join(parts) if parts else "no filters (broad search)"
