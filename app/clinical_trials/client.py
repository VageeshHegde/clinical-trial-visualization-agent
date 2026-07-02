from __future__ import annotations

from collections import Counter
from typing import Any

import requests

from app.clinical_trials.aggregation import (
    GROUP_BY_SCAN_FIELD,
    GROUP_BY_STATS_FIELD,
    buckets_from_counter,
    cap_buckets,
    dimension_filter_params,
    extract_group_values,
    filters_without_dimension,
    has_search_filters,
    label_group_value,
)
from app.clinical_trials.extract import extract_trial_summary
from app.clinical_trials.filters import StudySearchFilters
from app.clinical_trials.metadata import ENUM_GROUP_FIELDS, ClinicalTrialsMetadata
from app.config import Settings, get_settings
from app.models.schemas import AggregationBucket, TrialSummary

SUMMARY_FIELDS = [
    "protocolSection.identificationModule",
    "protocolSection.statusModule",
    "protocolSection.designModule",
    "protocolSection.conditionsModule",
    "protocolSection.sponsorCollaboratorsModule",
]


class ClinicalTrialsClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._timeout = self._settings.clinical_trials_timeout
        self._base_url = self._settings.clinical_trials_base_url.rstrip("/")
        self._max_page_size = self._settings.clinical_trials_max_page_size

        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": self._settings.clinical_trials_user_agent,
            }
        )
        self._metadata = ClinicalTrialsMetadata(
            self._session,
            self._base_url,
            self._timeout,
        )

    @property
    def metadata(self) -> ClinicalTrialsMetadata:
        return self._metadata

    def search_studies(
        self,
        filters: StudySearchFilters | None = None,
        *,
        page_size: int | None = None,
        page_token: str | None = None,
        include_total: bool = True,
    ) -> tuple[list[TrialSummary], str | None, int | None]:
        search_filters = filters or StudySearchFilters()
        params = self._build_search_params(search_filters)
        params["format"] = "json"
        effective_page_size = self._settings.clamp_agent_trial_limit(page_size)
        params["pageSize"] = min(max(effective_page_size, 1), self._max_page_size)
        params["fields"] = ",".join(SUMMARY_FIELDS)
        if include_total:
            params["countTotal"] = "true"
        if page_token:
            params["pageToken"] = page_token

        payload = self._get_json(f"{self._base_url}/studies", params=params)
        studies = payload.get("studies") or []
        trials = [extract_trial_summary(study) for study in studies]
        total_count = payload.get("totalCount")
        return trials, payload.get("nextPageToken"), total_count

    def get_study(self, nct_id: str) -> TrialSummary:
        response = self._session.get(
            f"{self._base_url}/studies/{nct_id}",
            params={"format": "json", "fields": ",".join(SUMMARY_FIELDS)},
            timeout=self._timeout,
        )
        response.raise_for_status()
        return extract_trial_summary(response.json())

    def count_studies(
        self,
        filters: StudySearchFilters | None = None,
        *,
        extra_params: dict[str, str] | None = None,
    ) -> int:
        params = self._build_search_params(filters or StudySearchFilters(), extra_params=extra_params)
        params["countTotal"] = "true"
        params["pageSize"] = 1
        payload = self._get_json(f"{self._base_url}/studies", params=params)
        return int(payload.get("totalCount") or 0)

    def count_by_field(
        self,
        group_by: str,
        filters: StudySearchFilters | None = None,
    ) -> tuple[list[AggregationBucket], int, str, bool, int]:
        search_filters = filters or StudySearchFilters()

        if not has_search_filters(search_filters):
            buckets, total, source = self._count_by_field_from_stats(group_by)
        elif group_by in ENUM_GROUP_FIELDS:
            buckets, total, source = self._count_by_field_from_totals(group_by, search_filters)
        else:
            buckets, total, source = self._count_by_field_from_scan(group_by, search_filters)

        return self._maybe_cap_buckets(group_by, buckets, total, source)

    def _maybe_cap_buckets(
        self,
        group_by: str,
        buckets: list[AggregationBucket],
        total: int,
        source: str,
    ) -> tuple[list[AggregationBucket], int, str, bool, int]:
        top_n = self._settings.aggregation_top_n
        capped_buckets, was_capped, buckets_total = cap_buckets(
            buckets,
            top_n=top_n,
            group_by=group_by,
        )
        return capped_buckets, total, source, was_capped, buckets_total

    def get_filter_options(self) -> dict[str, object]:
        return {
            "status_values": self._metadata.get_enum_values("OverallStatus"),
            "phase_values": self._metadata.get_enum_values("Phase"),
            "study_type_values": self._metadata.get_enum_values("StudyType"),
            "search_areas": self._metadata.get_search_area_query_params(),
            "query_params": self._metadata.get_supported_query_params(),
            "notes": "Values loaded from ClinicalTrials.gov /studies/enums and /studies/search-areas.",
        }

    def describe_search(self, filters: StudySearchFilters | None = None) -> str:
        return (filters or StudySearchFilters()).describe()

    def _count_by_field_from_stats(self, group_by: str) -> tuple[list[AggregationBucket], int, str]:
        field_name, field_type = GROUP_BY_STATS_FIELD[group_by]
        payload = self._get_json(
            f"{self._base_url}/stats/field/values",
            params={"fields": field_name, "types": field_type},
        )
        if not payload:
            return [], 0, "stats_api"

        stats = payload[0]
        buckets = [
            AggregationBucket(
                label=self._label_group_value(group_by, item["value"]),
                count=int(item["studiesCount"]),
            )
            for item in stats.get("topValues") or []
        ]
        total = self._get_json(f"{self._base_url}/stats/size").get("totalStudies") or 0
        return buckets, int(total), "stats_api"

    def _count_by_field_from_totals(
        self,
        group_by: str,
        filters: StudySearchFilters,
    ) -> tuple[list[AggregationBucket], int, str]:
        bucket_base = filters_without_dimension(group_by, filters)
        total = self.count_studies(filters)
        buckets: list[AggregationBucket] = []

        for raw_value in self._metadata.get_enum_group_values(group_by):
            count = self.count_studies(
                bucket_base,
                extra_params=dimension_filter_params(group_by, raw_value),
            )
            if count > 0:
                buckets.append(
                    AggregationBucket(
                        label=self._label_group_value(group_by, raw_value),
                        count=count,
                    )
                )

        buckets.sort(key=lambda bucket: bucket.count, reverse=True)
        return buckets, total, "count_total"

    def _count_by_field_from_scan(
        self,
        group_by: str,
        filters: StudySearchFilters,
    ) -> tuple[list[AggregationBucket], int, str]:
        params = self._build_search_params(filters)
        params["pageSize"] = self._settings.clinical_trials_scan_page_size
        params["fields"] = GROUP_BY_SCAN_FIELD[group_by]
        params["countTotal"] = "true"

        counter: Counter[str] = Counter()
        total: int | None = None
        page_token: str | None = None

        while True:
            page_params = dict(params)
            if page_token:
                page_params["pageToken"] = page_token

            payload = self._get_json(f"{self._base_url}/studies", params=page_params)
            if total is None:
                total = int(payload.get("totalCount") or 0)

            for study in payload.get("studies") or []:
                for raw_value in extract_group_values(study, group_by):
                    counter[raw_value] += 1

            page_token = payload.get("nextPageToken")
            if not page_token:
                break

        return (
            buckets_from_counter(
                group_by,
                counter,
                label_for=self._metadata.get_enum_label,
            ),
            total or 0,
            "full_scan",
        )

    def _label_group_value(self, group_by: str, raw_value: str) -> str:
        return label_group_value(
            group_by,
            raw_value,
            label_for=self._metadata.get_enum_label,
        )

    def _build_search_params(
        self,
        filters: StudySearchFilters,
        *,
        extra_params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}

        if filters.condition:
            params[self._metadata.get_query_param("condition")] = filters.condition
        if filters.intervention:
            params[self._metadata.get_query_param("intervention")] = filters.intervention
        if filters.sponsor:
            params[self._metadata.get_query_param("sponsor")] = filters.sponsor
        if filters.lead_sponsor:
            params[self._metadata.get_query_param("lead_sponsor")] = filters.lead_sponsor
        if filters.location:
            params[self._metadata.get_query_param("location")] = filters.location
        if filters.search_term:
            params[self._metadata.get_query_param("search_term")] = filters.search_term
        if filters.status:
            normalized_status = self._metadata.normalize_enum_list("OverallStatus", filters.status)
            params["filter.overallStatus"] = ",".join(normalized_status)
        if filters.nct_ids:
            params["filter.ids"] = ",".join(self._normalize_nct_ids(filters.nct_ids))
        if filters.agg_filters:
            params["aggFilters"] = ",".join(filters.agg_filters)
        if filters.sort:
            params["sort"] = filters.sort

        advanced = self._compose_advanced_filter(filters)
        if advanced:
            params["filter.advanced"] = advanced

        if extra_params:
            self._apply_extra_params(params, extra_params)
        return params

    def _compose_advanced_filter(self, filters: StudySearchFilters) -> str | None:
        parts: list[str] = []

        if filters.phase and filters.study_type:
            normalized_phase = self._metadata.normalize_enum_list("Phase", filters.phase)
            normalized_study_type = self._metadata.normalize_enum_list("StudyType", filters.study_type)
            parts.append(self._phase_filter_expression(normalized_phase))
            parts.append(self._study_type_filter_expression(normalized_study_type))
        elif filters.phase:
            normalized_phase = self._metadata.normalize_enum_list("Phase", filters.phase)
            parts.append(self._phase_filter_expression(normalized_phase))
        elif filters.study_type:
            normalized_study_type = self._metadata.normalize_enum_list("StudyType", filters.study_type)
            parts.append(self._study_type_filter_expression(normalized_study_type))

        if filters.advanced_filter:
            parts.append(f"({filters.advanced_filter})")

        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return " AND ".join(f"({part})" for part in parts)

    @staticmethod
    def _normalize_nct_ids(nct_ids: list[str]) -> list[str]:
        normalized: list[str] = []
        for nct_id in nct_ids:
            value = nct_id.strip().upper()
            if not value.startswith("NCT"):
                value = f"NCT{value}"
            normalized.append(value)
        return normalized

    @staticmethod
    def _apply_extra_params(params: dict[str, Any], extra_params: dict[str, str]) -> None:
        advanced = extra_params.get("filter.advanced")
        if advanced and params.get("filter.advanced"):
            params["filter.advanced"] = f"({params['filter.advanced']}) AND ({advanced})"
            for key, value in extra_params.items():
                if key != "filter.advanced":
                    params[key] = value
            return
        params.update(extra_params)

    @staticmethod
    def _phase_filter_expression(phases: list[str]) -> str:
        if len(phases) == 1:
            return f"AREA[Phase]{phases[0]}"
        joined = " OR ".join(f"AREA[Phase]{phase}" for phase in phases)
        return f"({joined})"

    @staticmethod
    def _study_type_filter_expression(study_types: list[str]) -> str:
        if len(study_types) == 1:
            return f"AREA[StudyType]{study_types[0]}"
        joined = " OR ".join(f"AREA[StudyType]{study_type}" for study_type in study_types)
        return f"({joined})"

    def _get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self._session.get(url, params=params, timeout=self._timeout)
        response.raise_for_status()
        return response.json()
