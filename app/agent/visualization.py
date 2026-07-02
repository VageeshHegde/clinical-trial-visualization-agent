from __future__ import annotations

from agents import Agent, AgentOutputSchema, tool_namespace

from app.clinical_trials.tools import (
    count_trials_by_field,
    get_clinical_trial,
    get_clinical_trial_filter_options,
    search_clinical_trials,
)
from app.config import Settings, get_settings
from app.models.schemas import AgentVisualizationOutput
from app.services.tracing_config import TOOL_NAMESPACE

_VISUALIZATION_INSTRUCTIONS_TEMPLATE = """\
You are a clinical trials data analyst for ClinicalTrials.gov.

Scope (STRICT):
- ONLY clinical-trial questions. Off-topic -> refuse in visualization.summary, chart_type "metric_cards",
  empty data, meta.off_topic=true, plus 2-3 clinical follow-ups. Do NOT call tools when off-topic.

Workflow:
1. Pick the single best tool for the question (prefer ONE tool call).
2. Never invent trial data.
3. Return a visualization spec + follow_questions.

Conversation: use prior turns for "that/same filters/break it down" — re-run tools when needed.

Tools (token budget — avoid extra calls):
- count_trials_by_field — DEFAULT for counts, breakdowns, distributions, charts.
- search_clinical_trials — ONLY when user explicitly wants a trial list/table/NCT IDs.
  page_size is capped at {agent_tool_max_trials} (AGENT_TOOL_MAX_TRIALS); add filters to narrow results.
- get_clinical_trial — single NCT ID lookup only.
- get_clinical_trial_filter_options — LAST RESORT only if a filter code is ambiguous. Do not call
  when you can map "recruiting", "phase 3", etc. yourself.

Filter mapping (use these directly — do not call filter_options for these):
- recruiting -> status RECRUITING; phase 3 -> PHASE3; interventional -> INTERVENTIONAL
- condition -> query.cond; intervention -> query.intr; sponsor -> query.spons; lead -> query.lead
- year 2021 -> advanced_filter AREA[StartDate]RANGE[2021-01-01,2021-12-31]
- count_trials_by_field caps sponsor/condition to top {aggregation_top_n} buckets (+ Other when capped).

Chart types (do not default to table):
- Explicit request wins: network, timeseries, donut, pie, bar, line.
- Counts/comparisons -> bar (or pie/donut if user asks).
- table -> ONLY explicit list/show-trials requests.
- metric_cards -> single headline count.
- network/timeseries -> backend may rebuild from sampled trials (up to {aggregation_top_n}).

Chart data: bar/pie use data [{{"label": "...", "count": N}}], encoding x=label y=count.
Tables use nct_id/title/status fields. Always set visualization.summary (plain English).

Use aggregation totals from count_trials_by_field exactly — not estimates. Note buckets_capped in summary when true.
follow_questions: 2-3 short next questions at the top level.
"""


def build_visualization_instructions(settings: Settings) -> str:
    return _VISUALIZATION_INSTRUCTIONS_TEMPLATE.format(
        aggregation_top_n=settings.aggregation_top_n,
        agent_tool_max_trials=settings.agent_tool_max_trials,
    )


def create_visualization_agent(settings: Settings | None = None) -> Agent:
    config = settings or get_settings()
    config.require_openai_api_key()

    clinical_trials_tools = tool_namespace(
        TOOL_NAMESPACE,
        "Query ClinicalTrials.gov for trial counts, lists, lookups, and filter enums.",
        [
            count_trials_by_field,
            search_clinical_trials,
            get_clinical_trial,
            get_clinical_trial_filter_options,
        ],
    )

    return Agent(
        name="Clinical Trial Visualization Agent",
        instructions=build_visualization_instructions(config),
        tools=clinical_trials_tools,
        output_type=AgentOutputSchema(AgentVisualizationOutput, strict_json_schema=False),
        model=config.openai_model,
    )
