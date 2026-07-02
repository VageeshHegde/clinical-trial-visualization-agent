from __future__ import annotations

import re

NCT_PATTERN = re.compile(r"\bNCT\d{8}\b", re.I)

CLINICAL_SIGNAL_PATTERN = re.compile(
    r"\b("
    r"trial|trials|clinical|recruiting|phase|sponsor|condition|intervention|"
    r"study|studies|enrollment|placebo|cohort|immunotherapy|vaccine|therapy|"
    r"drug|treatment|disease|nct|clinicaltrials|protocol|endpoint|"
    r"completed|terminated|withdrawn|active\s+not\s+recruiting"
    r")\b",
    re.I,
)

MATH_EXPRESSION_PATTERN = re.compile(
    r"^\s*\d+(?:\.\d+)?(?:\s*[-+*/x×]\s*\d+(?:\.\d+)?\s*)+[=?]?\s*$",
    re.I,
)

MATH_QUESTION_PATTERN = re.compile(
    r"\b(?:what\s+is|what's|calculate|compute|solve|sum\s+of)\b.*\d+\s*[-+*/x×]\s*\d+",
    re.I,
)

CHITCHAT_PATTERN = re.compile(
    r"^\s*(?:hi|hello|hey|thanks|thank you|bye|good\s+(?:morning|afternoon|evening))\b",
    re.I,
)

GENERAL_KNOWLEDGE_PATTERN = re.compile(
    r"\b(?:who is|when was|where is|capital of|define|explain|tell me a joke)\b",
    re.I,
)

FOLLOW_UP_PATTERN = re.compile(
    r"\b("
    r"that|those|same|it|them|this|previous|earlier|above|"
    r"break\s+(it|that)\s+down|as\s+a\s+(pie|bar|donut|line|table|network)|"
    r"show\s+(me\s+)?(that|them)|what\s+about|how\s+about|"
    r"instead|also|now|by\s+sponsor|by\s+phase|by\s+status|per\s+year|over\s+time"
    r")\b",
    re.I,
)

OFF_TOPIC_QUESTION_MESSAGE = (
    "question must be about clinical trials on ClinicalTrials.gov "
    "(e.g. trial counts, phases, sponsors, recruiting studies, or an NCT ID)"
)


def has_clinical_signal(question: str) -> bool:
    return bool(NCT_PATTERN.search(question) or CLINICAL_SIGNAL_PATTERN.search(question))


def is_math_question(question: str) -> bool:
    text = question.strip()
    return bool(MATH_EXPRESSION_PATTERN.match(text) or MATH_QUESTION_PATTERN.search(text))


def is_off_topic_question(question: str) -> bool:
    text = question.strip()
    if not text:
        return True
    if has_clinical_signal(text):
        return False
    if is_math_question(text):
        return True
    if CHITCHAT_PATTERN.match(text):
        return True
    if GENERAL_KNOWLEDGE_PATTERN.search(text):
        return True
    if len(text.split()) <= 4:
        return False
    return True


def is_clinical_follow_up(question: str, prior_messages: list[str]) -> bool:
    """Allow short contextual follow-ups when prior turns were about clinical trials."""
    text = question.strip()
    if not text or not prior_messages:
        return False
    if is_math_question(text) or CHITCHAT_PATTERN.match(text):
        return False
    if GENERAL_KNOWLEDGE_PATTERN.search(text):
        return False
    if not any(has_clinical_signal(message) for message in prior_messages):
        return False
    return bool(FOLLOW_UP_PATTERN.search(text) or len(text.split()) <= 12)
