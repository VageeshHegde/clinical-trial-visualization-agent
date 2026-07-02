from __future__ import annotations

import pytest

from app.models.schemas import ChartType, QueryRequest
from app.services.pipeline import answer_question


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question,allowed_chart_types",
    [
        (
            "How many recruiting diabetes trials are there by phase?",
            {ChartType.BAR, ChartType.PIE, ChartType.DONUT},
        ),
        (
            "List recruiting Parkinson's disease trials with NCT IDs",
            {ChartType.TABLE},
        ),
    ],
)
async def test_live_agent_chart_type(
    openai_api_key: str,
    question: str,
    allowed_chart_types: set[ChartType],
) -> None:
    _ = openai_api_key
    response = await answer_question(QueryRequest(question=question))
    assert response.visualization.summary.strip()
    assert response.visualization.data is not None
    assert response.visualization.chart_type in allowed_chart_types
    if response.follow_questions:
        assert all(question.strip() for question in response.follow_questions)
