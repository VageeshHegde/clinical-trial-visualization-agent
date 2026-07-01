from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    BAR = "bar"
    PIE = "pie"
    LINE = "line"
    TABLE = "table"
    METRIC_CARDS = "metric_cards"
    GROUPED_BAR = "grouped_bar"


class AxisEncoding(BaseModel):
    field: str = Field(description="Column name in the data array")
    label: str | None = Field(default=None, description="Human-readable axis label")


class ChartEncoding(BaseModel):
    x: str | None = Field(default=None, description="Data field for the x-axis or category")
    y: str | None = Field(default=None, description="Data field for the y-axis or value")
    color: str | None = Field(default=None, description="Data field for color grouping")
    label: str | None = Field(default=None, description="Data field for labels")
    value: str | None = Field(default=None, description="Data field for numeric values")


class VisualizationSpec(BaseModel):
    """Structured chart specification for frontend rendering."""

    chart_type: ChartType
    title: str
    summary: str = Field(description="Plain-language answer to the user's question")
    data: list[dict[str, Any]] = Field(
        description="Tabular rows the frontend maps to chart marks or table cells"
    )
    encoding: ChartEncoding = Field(
        default_factory=ChartEncoding,
        description="Maps visual channels to data fields",
    )
    x_axis: AxisEncoding | None = None
    y_axis: AxisEncoding | None = None
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Query context: filters applied, total trials, data source, etc.",
    )
    follow_questions: list[str] = Field(
        default_factory=list,
        description="2-3 suggested follow-up questions the user can ask next",
    )


class TrialSummary(BaseModel):
    nct_id: str
    title: str
    status: str | None = None
    phases: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    sponsor: str | None = None
    study_type: str | None = None
    enrollment: int | None = None
    start_date: str | None = None


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, description="Natural-language question about clinical trials")


class QueryResponse(BaseModel):
    question: str
    visualization: VisualizationSpec
    follow_questions: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions based on the current results",
    )
    trials: list[TrialSummary] = Field(
        default_factory=list,
        description="Sample of underlying trial records used in the analysis",
    )


class TrialSearchResult(BaseModel):
    total_returned: int
    has_more: bool
    trials: list[TrialSummary]
    search_description: str


class AggregationBucket(BaseModel):
    label: str
    count: int


class AggregationResult(BaseModel):
    group_by: str
    total_trials: int
    buckets: list[AggregationBucket]
    search_description: str
