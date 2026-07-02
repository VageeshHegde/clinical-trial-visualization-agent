from __future__ import annotations

from app.clinical_trials.compact import compact_search_result, compact_trial, truncate_text
from app.models.schemas import TrialSearchResult, TrialSummary


def test_truncate_text_adds_ellipsis() -> None:
    assert truncate_text("abcdefghij", max_len=6) == "abcde…"


def test_compact_trial_limits_title_and_conditions() -> None:
    trial = TrialSummary(
        nct_id="NCT00000001",
        title="A" * 200,
        conditions=["One", "Two", "Three"],
    )
    compact = compact_trial(trial, max_title_chars=50, max_conditions=2)
    assert len(compact.title) <= 50
    assert compact.conditions == ["One", "Two"]


def test_compact_search_result_caps_row_count() -> None:
    trials = [
        TrialSummary(nct_id=f"NCT{i:08d}", title=f"Trial {i}") for i in range(20)
    ]
    result = TrialSearchResult(
        total_returned=len(trials),
        total_count=100,
        has_more=True,
        trials=trials,
        search_description="condition='diabetes'",
    )
    compact = compact_search_result(
        result,
        max_trials=5,
        max_title_chars=80,
        max_conditions=2,
    )
    assert compact.total_returned == 5
    assert len(compact.trials) == 5
