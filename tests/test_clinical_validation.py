from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import ChatMessage, QueryRequest
from app.validation.clinical_question import (
    has_clinical_signal,
    is_clinical_follow_up,
    is_off_topic_question,
)
from evaluation import EvalCase, load_dataset


@pytest.mark.parametrize("case", load_dataset(), ids=lambda case: case.id)
def test_eval_request_validation(case: EvalCase) -> None:
    history = [ChatMessage.model_validate(message) for message in (case.history or [])]
    if case.expect.valid_request:
        request = QueryRequest(question=case.question, history=history)
        assert request.question == case.question
    else:
        with pytest.raises(ValidationError):
            QueryRequest(question=case.question, history=history)


@pytest.mark.parametrize("case", load_dataset(), ids=lambda case: case.id)
def test_eval_off_topic_classification(case: EvalCase) -> None:
    if case.category == "off_topic":
        assert is_off_topic_question(case.question)
    elif case.category != "follow_up":
        assert not is_off_topic_question(case.question)


def test_clinical_signal_detects_trial_vocabulary() -> None:
    assert has_clinical_signal("How many phase 3 oncology trials are recruiting?")
    assert has_clinical_signal("Details for NCT04380701")


def test_follow_up_requires_prior_clinical_context() -> None:
    assert is_clinical_follow_up(
        "Break that down by sponsor",
        ["How many lung cancer trials are recruiting?"],
    )
    assert not is_clinical_follow_up(
        "Break that down by sponsor",
        ["What is the weather today?"],
    )
