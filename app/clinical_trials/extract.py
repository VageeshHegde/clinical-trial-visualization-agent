from __future__ import annotations

from typing import Any

from app.models.schemas import TrialSummary

PHASE_LABELS = {
    "EARLY_PHASE1": "Early Phase 1",
    "PHASE1": "Phase 1",
    "PHASE2": "Phase 2",
    "PHASE3": "Phase 3",
    "PHASE4": "Phase 4",
    "NA": "N/A",
}

STATUS_LABELS = {
    "RECRUITING": "Recruiting",
    "ACTIVE_NOT_RECRUITING": "Active, not recruiting",
    "COMPLETED": "Completed",
    "ENROLLING_BY_INVITATION": "Enrolling by invitation",
    "NOT_YET_RECRUITING": "Not yet recruiting",
    "SUSPENDED": "Suspended",
    "TERMINATED": "Terminated",
    "WITHDRAWN": "Withdrawn",
    "AVAILABLE": "Available",
    "NO_LONGER_AVAILABLE": "No longer available",
    "TEMPORARILY_NOT_AVAILABLE": "Temporarily not available",
    "APPROVED_FOR_MARKETING": "Approved for marketing",
    "WITHHELD": "Withheld",
    "UNKNOWN": "Unknown",
}


def humanize_phase(phase: str) -> str:
    return PHASE_LABELS.get(phase, phase.replace("_", " ").title())


def humanize_status(status: str) -> str:
    return STATUS_LABELS.get(status, status.replace("_", " ").title())


def extract_trial_summary(study: dict[str, Any]) -> TrialSummary:
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    status_module = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    conditions_module = protocol.get("conditionsModule", {})
    sponsor_module = protocol.get("sponsorCollaboratorsModule", {})

    enrollment_info = design.get("enrollmentInfo") or {}
    start_date_struct = status_module.get("startDateStruct") or {}

    return TrialSummary(
        nct_id=identification.get("nctId", "UNKNOWN"),
        title=identification.get("briefTitle") or identification.get("officialTitle") or "Untitled",
        status=status_module.get("overallStatus"),
        phases=design.get("phases") or [],
        conditions=conditions_module.get("conditions") or [],
        sponsor=(sponsor_module.get("leadSponsor") or {}).get("name"),
        study_type=design.get("studyType"),
        enrollment=enrollment_info.get("count"),
        start_date=start_date_struct.get("date"),
    )
