from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
DATASET_PATH = EVAL_DIR / "dataset.json"
FIXTURES_DIR = EVAL_DIR / "fixtures"


@dataclass(frozen=True)
class EvalExpectations:
    valid_request: bool
    preferred_chart_type: str | None = None
    asks_for_breakdown: bool | None = None
    asks_for_list: bool | None = None
    enhanced_chart_type_with_aggregation: str | None = None
    enhanced_chart_type_with_trials: str | None = None
    enhanced_chart_type_with_small_aggregation: str | None = None


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    category: str
    expect: EvalExpectations
    history: list[dict[str, str]] | None = None


def load_dataset() -> list[EvalCase]:
    raw = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    cases: list[EvalCase] = []
    for entry in raw["cases"]:
        expect_raw = entry["expect"]
        expect = EvalExpectations(
            valid_request=expect_raw["valid_request"],
            preferred_chart_type=expect_raw.get("preferred_chart_type"),
            asks_for_breakdown=expect_raw.get("asks_for_breakdown"),
            asks_for_list=expect_raw.get("asks_for_list"),
            enhanced_chart_type_with_aggregation=expect_raw.get(
                "enhanced_chart_type_with_aggregation"
            ),
            enhanced_chart_type_with_trials=expect_raw.get("enhanced_chart_type_with_trials"),
            enhanced_chart_type_with_small_aggregation=expect_raw.get(
                "enhanced_chart_type_with_small_aggregation"
            ),
        )
        cases.append(
            EvalCase(
                id=entry["id"],
                question=entry["question"],
                category=entry["category"],
                expect=expect,
                history=entry.get("history"),
            )
        )
    return cases


def load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))
