from collections.abc import Iterator
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import get_settings


def get_client() -> OpenAI:
    settings = get_settings()
    kwargs = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
def stream_completion(messages: list[dict]) -> Iterator:
    # Retries cover failures while creating the provider stream. A network failure
    # after chunks have been sent cannot safely restart the same HTTP response.
    client = get_client()
    return client.chat.completions.create(
        model=get_settings().openai_model,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},
    )


def estimate_tokens(text: str) -> int:
    # Fallback only; provider-reported usage is preferred.
    return max(1, len(text) // 4)


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    settings = get_settings()
    return (
        input_tokens * settings.input_cost_per_1m
        + output_tokens * settings.output_cost_per_1m
    ) / 1_000_000
