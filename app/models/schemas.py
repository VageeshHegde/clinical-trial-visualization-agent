from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from app.validation.clinical_question import OFF_TOPIC_QUESTION_MESSAGE, is_off_topic_question


class ChartType(str, Enum):
    BAR = "bar"
    PIE = "pie"
    DONUT = "donut"
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


class AgentVisualizationOutput(BaseModel):
    """Structured agent output: chart spec plus suggested follow-ups."""

    visualization: VisualizationSpec
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
    """API/CLI input: a single clinical-trials question string."""

    model_config = ConfigDict(str_strip_whitespace=True)

    question: Annotated[
        StrictStr,
        Field(
            min_length=1,
            max_length=2000,
            description="Natural-language question about clinical trials",
            examples=["How many recruiting diabetes trials are in phase 3?"],
        ),
    ]

    @field_validator("question", mode="before")
    @classmethod
    def question_must_be_string(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, str):
            raise ValueError("question must be a string")
        return value

    @field_validator("question")
    @classmethod
    def question_must_be_clinical_trials(cls, value: str) -> str:
        if is_off_topic_question(value):
            raise ValueError(OFF_TOPIC_QUESTION_MESSAGE)
        return value


class QueryResponse(BaseModel):
    question: str
    visualization: VisualizationSpec
    follow_questions: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions based on the current results",
    )
    trials: list[TrialSummary] = Field(
        default_factory=list,
        description="Source trial records (NCT IDs) sampled for the analysis; supports traceability",
    )


class TrialSearchResult(BaseModel):
    total_returned: int
    total_count: int | None = Field(
        default=None,
        description="Total matching studies from ClinicalTrials.gov countTotal, when available",
    )
    has_more: bool
    trials: list[TrialSummary]
    search_description: str


class FilterOptionsResult(BaseModel):
    status_values: list[str]
    phase_values: list[str]
    study_type_values: list[str]
    search_areas: dict[str, str]
    query_params: dict[str, str]
    notes: str


class AggregationBucket(BaseModel):
    label: str
    count: int


class AggregationResult(BaseModel):
    group_by: str
    total_trials: int
    buckets: list[AggregationBucket]
    search_description: str
    data_source: str = Field(
        default="stats_api",
        description="How counts were computed: stats_api, count_total, or full_scan",
    )
    buckets_capped: bool = Field(
        default=False,
        description="True when only the top N buckets were returned (remainder grouped as Other)",
    )
    buckets_total: int | None = Field(
        default=None,
        description="Total distinct bucket count before capping, when buckets_capped is true",
    )
    trials: list[TrialSummary] = Field(
        default_factory=list,
        description="Optional trial records for traceability; usually empty for exact aggregations",
    )
