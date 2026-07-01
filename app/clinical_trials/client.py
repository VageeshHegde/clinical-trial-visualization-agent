from __future__ import annotations

from typing import Any

import requests

from app.clinical_trials.extract import extract_trial_summary
from app.config import Settings, get_settings
from app.models.schemas import TrialSummary

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

    def search_studies(
        self,
        *,
        condition: str | None = None,
        intervention: str | None = None,
        sponsor: str | None = None,
        search_term: str | None = None,
        status: list[str] | None = None,
        phase: list[str] | None = None,
        page_size: int = 50,
        page_token: str | None = None,
    ) -> tuple[list[TrialSummary], str | None]:
        params: dict[str, Any] = {
            "format": "json",
            "pageSize": min(max(page_size, 1), self._max_page_size),
            "fields": ",".join(SUMMARY_FIELDS),
        }
        if condition:
            params["query.cond"] = condition
        if intervention:
            params["query.intr"] = intervention
        if sponsor:
            params["query.spons"] = sponsor
        if search_term:
            params["query.term"] = search_term
        if status:
            params["filter.overallStatus"] = status
        if phase:
            params["filter.phase"] = phase
        if page_token:
            params["pageToken"] = page_token

        response = self._session.get(
            f"{self._base_url}/studies",
            params=params,
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()

        studies = payload.get("studies") or []
        trials = [extract_trial_summary(study) for study in studies]
        return trials, payload.get("nextPageToken")

    def get_study(self, nct_id: str) -> TrialSummary:
        response = self._session.get(
            f"{self._base_url}/studies/{nct_id}",
            params={"format": "json", "fields": ",".join(SUMMARY_FIELDS)},
            timeout=self._timeout,
        )
        response.raise_for_status()
        return extract_trial_summary(response.json())

    def describe_search(
        self,
        *,
        condition: str | None = None,
        intervention: str | None = None,
        sponsor: str | None = None,
        search_term: str | None = None,
        status: list[str] | None = None,
        phase: list[str] | None = None,
    ) -> str:
        parts: list[str] = []
        if condition:
            parts.append(f"condition={condition!r}")
        if intervention:
            parts.append(f"intervention={intervention!r}")
        if sponsor:
            parts.append(f"sponsor={sponsor!r}")
        if search_term:
            parts.append(f"term={search_term!r}")
        if status:
            parts.append(f"status={', '.join(status)}")
        if phase:
            parts.append(f"phase={', '.join(phase)}")
        return "; ".join(parts) if parts else "no filters (broad search)"
