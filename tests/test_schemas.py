from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    AgentVisualizationOutput,
    ChartType,
    QueryRequest,
    QueryResponse,
    VisualizationSpec,
)
from evaluation import load_fixture


class TestQueryRequestValidation:
    def test_accepts_clinical_question(self) -> None:
        request = QueryRequest(question="How many recruiting diabetes trials are there by phase?")
        assert request.question.startswith("How many")

    def test_rejects_off_topic_question(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(question="What is 2 + 2?")
        assert "clinical trials" in str(exc_info.value).lower()

    def test_accepts_follow_up_with_clinical_history(self) -> None:
        request = QueryRequest(
            question="Break that down by sponsor",
            history=[
                {"role": "user", "content": "How many lung cancer trials are recruiting?"},
                {"role": "assistant", "content": "There are 412 recruiting lung cancer trials."},
            ],
        )
        assert request.question == "Break that down by sponsor"

    def test_rejects_non_string_question(self) -> None:
        with pytest.raises(ValidationError):
            QueryRequest.model_validate({"question": 42})


class TestVisualizationSpecValidation:
    def test_requires_chart_type_and_title(self) -> None:
        with pytest.raises(ValidationError):
            VisualizationSpec.model_validate({"title": "Missing chart type", "data": []})

    def test_auto_fills_summary_when_missing(self) -> None:
        spec = VisualizationSpec.model_validate(
            {
                "chart_type": "bar",
                "title": "Trials by phase",
                "data": [{"label": "Phase 2", "count": 3}],
                "meta": {"total_trials": 3},
            }
        )
        assert spec.summary
        assert "3" in spec.summary

    def test_rejects_unknown_chart_type(self) -> None:
        with pytest.raises(ValidationError):
            VisualizationSpec.model_validate(
                {
                    "chart_type": "scatter",
                    "title": "Invalid chart",
                    "summary": "Should fail",
                    "data": [],
                }
            )


class TestResponseFixtures:
    def test_sample_query_response_matches_schema(self) -> None:
        payload = load_fixture("sample_query_response.json")
        response = QueryResponse.model_validate(payload)
        assert response.visualization.chart_type == ChartType.BAR
        assert response.follow_questions
        assert response.trials[0].nct_id.startswith("NCT")

    def test_sample_agent_output_matches_schema(self) -> None:
        payload = load_fixture("sample_agent_output.json")
        output = AgentVisualizationOutput.model_validate(payload)
        assert output.visualization.chart_type == ChartType.METRIC_CARDS
        assert len(output.follow_questions) >= 2
