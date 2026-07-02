from __future__ import annotations

TOKEN_RATE_LIMIT_MESSAGE = (
    "OpenAI token rate limit exceeded (TPM). This request needed more tokens than your "
    "organization allows per minute (often ~30k on gpt-4.1). Common causes: listing too "
    "many trials at once, broad sponsor/condition breakdowns, or retrying too quickly. "
    "Try a narrower question (add condition, status, phase, or year filters), avoid "
    "large trial lists, set OPENAI_MODEL=gpt-4.1-mini in .env, or wait about a minute "
    "and retry. Trial lists and chart samples are capped by AGGREGATION_TOP_N in .env."
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
