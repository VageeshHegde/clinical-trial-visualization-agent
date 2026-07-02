from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from app.validation.clinical_question import (
    OFF_TOPIC_QUESTION_MESSAGE,
    is_clinical_follow_up,
    is_off_topic_question,
)


class ChartType(str, Enum):
    BAR = "bar"
    PIE = "pie"
    DONUT = "donut"
    LINE = "line"
    TABLE = "table"
    METRIC_CARDS = "metric_cards"
    GROUPED_BAR = "grouped_bar"
    NETWORK = "network"
    TIMESERIES = "timeseries"


class AxisEncoding(BaseModel):
    field: str = Field(description="Column name in the data array")
    label: str | None = Field(default=None, description="Human-readable axis label")


class ChartEncoding(BaseModel):
    x: str | None = Field(default=None, description="Data field for the x-axis or category")
    y: str | None = Field(default=None, description="Data field for the y-axis or value")
    color: str | None = Field(default=None, description="Data field for color grouping")
    label: str | None = Field(default=None, description="Data field for labels")
    value: str | None = Field(default=None, description="Data field for numeric values")


def _default_visualization_summary(data: dict[str, Any]) -> str:
    title = str(data.get("title") or "Clinical trial results")
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    total = meta.get("total_trials")
    rows = data.get("data")
    row_count = len(rows) if isinstance(rows, list) else 0

    if total is not None:
        suffix = f"; showing {row_count} in this view." if row_count else "."
        return f"{title}. ClinicalTrials.gov reports {int(total):,} matching trials{suffix}"

    if row_count:
        return f"{title}. Showing {row_count} trial(s) from the search."

    return title


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

    @model_validator(mode="before")
    @classmethod
    def ensure_summary(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        summary = data.get("summary")
        if summary is None or (isinstance(summary, str) and not summary.strip()):
            data["summary"] = _default_visualization_summary(data)
        return data


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


class ChatMessage(BaseModel):
    """One turn in the chat transcript sent for multi-turn context."""

    model_config = ConfigDict(str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: Annotated[
        StrictStr,
        Field(
            min_length=1,
            max_length=4000,
            description="Message text (assistant summaries, not full chart JSON)",
        ),
    ]


class QueryRequest(BaseModel):
    """API/CLI input: current question plus optional prior chat turns."""

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
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Prior user/assistant messages; server keeps the last CHAT_CONTEXT_MAX_MESSAGES",
    )

    @field_validator("question", mode="before")
    @classmethod
    def question_must_be_string(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, str):
            raise ValueError("question must be a string")
        return value

    @model_validator(mode="after")
    def question_must_be_clinical_trials(self) -> QueryRequest:
        if not is_off_topic_question(self.question):
            return self
        prior = [message.content for message in self.history]
        if is_clinical_follow_up(self.question, prior):
            return self
        raise ValueError(OFF_TOPIC_QUESTION_MESSAGE)


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
    search_areas: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, str] = Field(default_factory=dict)
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
