from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

GROUP_BY_ENUM_PIECE: dict[str, str] = {
    "status": "OverallStatus",
    "phase": "Phase",
    "study_type": "StudyType",
}

ENUM_GROUP_FIELDS = frozenset(GROUP_BY_ENUM_PIECE)


@dataclass(frozen=True)
class EnumEntry:
    value: str
    legacy_value: str | None = None


class ClinicalTrialsMetadata:
    def __init__(
        self,
        session: requests.Session,
        base_url: str,
        timeout: float,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._enums_by_piece: dict[str, list[EnumEntry]] | None = None
        self._search_area_params: dict[str, str] | None = None

    def get_enum_values(self, piece: str) -> list[str]:
        return [entry.value for entry in self._load_enums().get(piece, [])]

    def get_enum_group_values(self, group_by: str) -> list[str]:
        piece = GROUP_BY_ENUM_PIECE.get(group_by)
        if piece is None:
            raise KeyError(f"No enum mapping for group_by={group_by!r}")
        return self.get_enum_values(piece)

    def get_enum_label(self, piece: str, value: str) -> str:
        for entry in self._load_enums().get(piece, []):
            if entry.value == value:
                return entry.legacy_value or _titleize_enum(value)
        return _titleize_enum(value)

    def get_group_label(self, group_by: str, value: str) -> str:
        piece = GROUP_BY_ENUM_PIECE.get(group_by)
        if piece is None:
            return value
        return self.get_enum_label(piece, value)

    def normalize_enum(self, piece: str, raw_value: str) -> str:
        normalized = raw_value.strip()
        if not normalized:
            raise ValueError(f"Empty value for {piece}")

        enums = self._load_enums().get(piece, [])
        if not enums:
            raise ValueError(f"Unknown enum piece: {piece}")

        candidates = {
            normalized,
            normalized.upper(),
            normalized.replace(" ", "_").upper(),
            normalized.replace("-", "_").upper(),
        }
        if normalized.lower().startswith("phase ") and len(normalized.split()) == 2:
            candidates.add(f"PHASE{normalized.split()[1]}")

        for entry in enums:
            if entry.value in candidates:
                return entry.value
            if entry.legacy_value and entry.legacy_value.lower() == normalized.lower():
                return entry.value

        valid = ", ".join(entry.value for entry in enums)
        raise ValueError(f"Invalid {piece} value {raw_value!r}. Valid values: {valid}")

    def normalize_enum_list(self, piece: str, values: list[str]) -> list[str]:
        return [self.normalize_enum(piece, value) for value in values]

    def get_query_param(self, filter_name: str) -> str:
        mapping = {
            "condition": "cond",
            "intervention": "intr",
            "sponsor": "spons",
            "lead_sponsor": "lead",
            "location": "locn",
            "search_term": "term",
        }
        area_param = mapping.get(filter_name)
        if area_param is None:
            raise KeyError(f"No search area mapping for filter {filter_name!r}")
        return f"query.{self._load_search_area_params().get(area_param, area_param)}"

    def get_search_area_query_params(self) -> dict[str, str]:
        return {
            "condition": self.get_query_param("condition"),
            "intervention": self.get_query_param("intervention"),
            "sponsor": self.get_query_param("sponsor"),
            "lead_sponsor": self.get_query_param("lead_sponsor"),
            "location": self.get_query_param("location"),
            "search_term": self.get_query_param("search_term"),
        }

    def get_supported_query_params(self) -> dict[str, str]:
        return {
            **self.get_search_area_query_params(),
            "status": "filter.overallStatus",
            "phase": "filter.advanced (AREA[Phase]…)",
            "study_type": "filter.advanced (AREA[StudyType]…)",
            "nct_ids": "filter.ids",
            "agg_filters": "aggFilters",
            "advanced_filter": "filter.advanced",
            "sort": "sort",
            "count_total": "countTotal",
            "page_size": "pageSize",
            "page_token": "pageToken",
            "fields": "fields",
        }

    def format_filter_guide(self) -> str:
        status = ", ".join(self.get_enum_values("OverallStatus"))
        phase = ", ".join(self.get_enum_values("Phase"))
        study_type = ", ".join(self.get_enum_values("StudyType"))
        areas = self.get_search_area_query_params()
        params = self.get_supported_query_params()
        return (
            "Validated ClinicalTrials.gov filter values (from /studies/enums and /studies/search-areas):\n"
            f"- status ({params['status']}): {status}\n"
            f"- phase ({params['phase']}): {phase}\n"
            f"- study_type ({params['study_type']}): {study_type}\n"
            "- search areas -> query params:\n"
            f"  - condition -> {areas['condition']}\n"
            f"  - intervention -> {areas['intervention']}\n"
            f"  - sponsor -> {areas['sponsor']}\n"
            f"  - lead sponsor -> {areas['lead_sponsor']}\n"
            f"  - location -> {areas['location']}\n"
            f"  - general term -> {areas['search_term']}\n"
            "- other supported params: filter.ids, aggFilters, filter.advanced, sort, countTotal\n"
            "Use these exact enum codes when setting status, phase, or study_type filters."
        )

    def _load_enums(self) -> dict[str, list[EnumEntry]]:
        if self._enums_by_piece is not None:
            return self._enums_by_piece

        payload = self._get_json(f"{self._base_url}/studies/enums")
        enums_by_piece: dict[str, list[EnumEntry]] = {}

        for item in payload:
            values = item.get("values") or []
            entries = [
                EnumEntry(
                    value=str(entry["value"]),
                    legacy_value=entry.get("legacyValue"),
                )
                for entry in values
                if entry.get("value") is not None
            ]
            for piece in item.get("pieces") or []:
                enums_by_piece.setdefault(piece, []).extend(entries)

        self._enums_by_piece = enums_by_piece
        return self._enums_by_piece

    def _load_search_area_params(self) -> dict[str, str]:
        if self._search_area_params is not None:
            return self._search_area_params

        payload = self._get_json(f"{self._base_url}/studies/search-areas")
        params: dict[str, str] = {}

        for group in payload:
            for area in group.get("areas") or []:
                param = area.get("param")
                if param:
                    params[param] = param

        self._search_area_params = params
        return self._search_area_params

    def _get_json(self, url: str) -> Any:
        response = self._session.get(url, timeout=self._timeout)
        response.raise_for_status()
        return response.json()


def _titleize_enum(value: str) -> str:
    return value.replace("_", " ").title()
