from __future__ import annotations

TOKEN_RATE_LIMIT_MESSAGE = (
    "OpenAI token rate limit exceeded (TPM). The request was too large for your "
    "organization's model quota — often caused by very large breakdowns (e.g. by sponsor) "
    "or verbose tool payloads sent to the model. "
    "Try narrowing your question with filters (condition, status, year, location), "
    "set OPENAI_MODEL=gpt-4.1-mini in .env, or wait about a minute and retry. "
    "This app caps sponsor/condition breakdowns to the top N categories to keep responses within limits."
)


def is_token_rate_limit_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return (
        "429" in message
        or "rate_limit_exceeded" in message
        or "tokens per min" in message
        or "request too large" in message
        or ("tpm" in message and "limit" in message)
    )
