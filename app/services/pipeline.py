from __future__ import annotations

from agents import Runner

from app.agent.visualization import create_visualization_agent
from app.config import get_settings
from app.models.schemas import QueryRequest, QueryResponse, TrialSummary, VisualizationSpec
from app.services.visualization_builder import enhance_visualization


async def answer_question(request: QueryRequest) -> QueryResponse:
    settings = get_settings()
    settings.apply()
    settings.require_openai_api_key()

    agent = create_visualization_agent(settings)
    result = await Runner.run(agent, request.question)

    visualization = result.final_output
    if not isinstance(visualization, VisualizationSpec):
        raise TypeError("Agent did not return a VisualizationSpec")

    visualization = enhance_visualization(request.question, result, visualization)

    trials = _extract_trials_from_run(result)

    return QueryResponse(
        question=request.question,
        visualization=visualization,
        follow_questions=visualization.follow_questions,
        trials=trials,
    )


def _extract_trials_from_run(result: object) -> list[TrialSummary]:
    """Collect trial summaries from tool outputs when available."""
    trials: list[TrialSummary] = []
    new_items = getattr(result, "new_items", None)
    if not new_items:
        return trials

    for item in new_items:
        if getattr(item, "type", None) != "tool_call_output_item":
            continue
        output = getattr(item, "output", None)
        if output is None:
            continue
        _collect_trials(output, trials)

    seen: set[str] = set()
    unique: list[TrialSummary] = []
    for trial in trials:
        if trial.nct_id in seen:
            continue
        seen.add(trial.nct_id)
        unique.append(trial)
    return unique[:25]


def _collect_trials(output: object, trials: list[TrialSummary]) -> None:
    if isinstance(output, TrialSummary):
        trials.append(output)
        return

    trials_attr = getattr(output, "trials", None)
    if isinstance(trials_attr, list):
        for trial in trials_attr:
            if isinstance(trial, TrialSummary):
                trials.append(trial)
