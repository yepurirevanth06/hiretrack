"""One small interface in front of every LLM call.

Services depend on `LLMClient`, not on the Anthropic SDK, so tests can swap in
`FakeLLM` (no network, no cost, same answer every time) and the provider could
change later without touching business code.
"""

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import anthropic
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import AIOutputError, AIUnavailableError


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    output: T
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class LLMClient(Protocol):
    def extract[T: BaseModel](
        self, *, system: str, user: str, schema: type[T], max_tokens: int = 2048
    ) -> LLMResult[T]: ...


class AnthropicLLM:
    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self.client = client
        self.model = model

    def extract[T: BaseModel](
        self, *, system: str, user: str, schema: type[T], max_tokens: int = 2048
    ) -> LLMResult[T]:
        started = time.perf_counter()
        try:
            # Structured outputs: the API constrains the answer to the JSON
            # schema of `schema`, and the SDK validates it into that model.
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
            )
        except anthropic.APIStatusError as exc:
            if exc.status_code in (401, 403):
                raise AIUnavailableError(
                    "AI provider rejected our credentials"
                ) from exc
            raise AIUnavailableError("AI provider returned an error") from exc
        except anthropic.APIError as exc:  # connection errors and timeouts
            raise AIUnavailableError("AI provider is unreachable") from exc

        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise AIOutputError("AI response was incomplete or didn't match the schema")

        return LLMResult(
            output=response.parsed_output,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )


@lru_cache
def _anthropic_llm(api_key: str, model: str, timeout: float) -> AnthropicLLM:
    # The SDK already retries rate limits (429) and server errors (5xx) with
    # exponential backoff; we keep that, and cap the total wait with a timeout.
    client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)
    return AnthropicLLM(client, model)


def get_llm() -> LLMClient:
    """FastAPI dependency. Tests override it with a FakeLLM."""
    if settings.llm_provider == "fake":
        from app.ai.fake import FakeLLM

        return FakeLLM()
    if not settings.anthropic_api_key:
        raise AIUnavailableError("AI is not configured: set ANTHROPIC_API_KEY in .env")
    return _anthropic_llm(
        settings.anthropic_api_key, settings.llm_model, settings.llm_timeout_seconds
    )
