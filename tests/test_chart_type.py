from __future__ import annotations

import pytest

from app.models.schemas import ChartType
from app.services.visualization_builder import (
    _asks_for_breakdown,
    _asks_for_list,
    _preferred_chart_type,
    enhance_visualization,
)
from evaluation import load_dataset
from tests.helpers import (
    make_aggregation_result,
    make_base_visualization,
    make_run_with_aggregation,
    make_sample_trials,
    make_small_aggregation_result,
)


@pytest.mark.parametrize("case", load_dataset(), ids=lambda case: case.id)
def test_eval_question_intent(case) -> None:
    if case.expect.preferred_chart_type is not None:
        preferred = _preferred_chart_type(case.question)
        assert preferred is not None
        assert preferred.value == case.expect.preferred_chart_type

    if case.expect.asks_for_breakdown is not None:
        assert _asks_for_breakdown(case.question) is case.expect.asks_for_breakdown

    if case.expect.asks_for_list is not None:
        assert _asks_for_list(case.question) is case.expect.asks_for_list


@pytest.mark.parametrize("case", load_dataset(), ids=lambda case: case.id)
def test_eval_enhanced_chart_type_with_aggregation(case) -> None:
    expected = case.expect.enhanced_chart_type_with_aggregation
    if expected is None:
        pytest.skip("No aggregation chart expectation for this case")

    visualization = make_base_visualization(chart_type="table")
    result = make_run_with_aggregation(make_aggregation_result())
    enhanced = enhance_visualization(case.question, result, visualization)

    assert enhanced.chart_type.value == expected
    assert enhanced.data
    assert all("label" in row and "count" in row for row in enhanced.data)


@pytest.mark.parametrize("case", load_dataset(), ids=lambda case: case.id)
def test_eval_enhanced_chart_type_with_trials(case) -> None:
    expected = case.expect.enhanced_chart_type_with_trials
    if expected is None:
        pytest.skip("No trial-based chart expectation for this case")

    visualization = make_base_visualization(chart_type="table")
    trials = make_sample_trials()
    enhanced = enhance_visualization(
        case.question,
        make_run_with_aggregation(make_aggregation_result()),
        visualization,
        trials=trials,
    )

    assert enhanced.chart_type.value == expected


def test_small_bucket_aggregation_prefers_pie() -> None:
    case = next(case for case in load_dataset() if case.id == "small_bucket_pie")
    expected = case.expect.enhanced_chart_type_with_small_aggregation
    assert expected == "pie"

    visualization = make_base_visualization(chart_type="table")
    result = make_run_with_aggregation(make_small_aggregation_result())
    enhanced = enhance_visualization(case.question, result, visualization)
    assert enhanced.chart_type == ChartType.PIE
    assert len(enhanced.data) == 4


def test_list_questions_keep_agent_table() -> None:
    visualization = make_base_visualization(chart_type="table")
    enhanced = enhance_visualization(
        "List recruiting Parkinson's disease trials with NCT IDs",
        make_run_with_aggregation(make_aggregation_result()),
        visualization,
    )
    assert enhanced.chart_type == ChartType.TABLE
