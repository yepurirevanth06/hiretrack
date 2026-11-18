"""The real Anthropic client, tested without the network: the SDK client is
replaced by a stub, so we check our own mapping of results and errors."""

import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2 as httpx  # the HTTP library the Anthropic SDK uses
import pytest

from app.ai import llm as llm_module
from app.ai.llm import AnthropicLLM, get_llm
from app.ai.resume_parser import ParsedResume
from app.core.exceptions import AIOutputError, AIUnavailableError

PARSED = ParsedResume(
    summary="s",
    skills=["Python"],
    total_years_experience=2,
    experience=[],
    education=[],
)
REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def llm_returning(**response: Any) -> tuple[AnthropicLLM, dict]:
    calls: dict[str, Any] = {}

    def parse(**kwargs: Any) -> SimpleNamespace:
        calls.update(kwargs)
        if "error" in response:
            raise response["error"]
        return SimpleNamespace(
            parsed_output=response.get("parsed", PARSED),
            stop_reason=response.get("stop_reason", "end_turn"),
            model="claude-haiku-5-5",
            usage=SimpleNamespace(input_tokens=1200, output_tokens=300),
        )

    client = SimpleNamespace(messages=SimpleNamespace(parse=parse))
    return AnthropicLLM(client, "claude-haiku-5-5"), calls  # type: ignore[arg-type]


def extract(llm: AnthropicLLM):
    return llm.extract(system="sys", user="resume text", schema=ParsedResume)


def test_a_successful_call_returns_the_parsed_output_and_usage() -> None:
    llm, calls = llm_returning()

    result = extract(llm)

    assert result.output == PARSED
    assert (result.input_tokens, result.output_tokens) == (1200, 300)
    assert calls["output_format"] is ParsedResume  # structured outputs are requested
    assert calls["system"] == "sys"


@pytest.mark.parametrize(
    "error",
    [
        anthropic.APIConnectionError(request=REQUEST),
        anthropic.APITimeoutError(request=REQUEST),
        anthropic.RateLimitError(
            "slow down", response=httpx.Response(429, request=REQUEST), body=None
        ),
        anthropic.AuthenticationError(
            "bad key", response=httpx.Response(401, request=REQUEST), body=None
        ),
    ],
)
def test_provider_failures_become_503(error: Exception) -> None:
    llm, _ = llm_returning(error=error)

    with pytest.raises(AIUnavailableError):
        extract(llm)


@pytest.mark.parametrize("response", [{"parsed": None}, {"stop_reason": "max_tokens"}])
def test_unusable_answers_become_502(response: dict) -> None:
    llm, _ = llm_returning(**response)

    with pytest.raises(AIOutputError):
        extract(llm)


def test_missing_api_key_is_reported_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_module.settings, "llm_provider", "anthropic")
    monkeypatch.setattr(llm_module.settings, "anthropic_api_key", None)

    with pytest.raises(AIUnavailableError, match="ANTHROPIC_API_KEY"):
        get_llm()


def test_the_fake_provider_needs_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_module.settings, "llm_provider", "fake")

    assert get_llm().model == "fake-llm"  # type: ignore[attr-defined]


def test_the_real_client_is_built_once_and_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm_module.settings, "llm_provider", "anthropic")
    monkeypatch.setattr(llm_module.settings, "anthropic_api_key", "sk-ant-test")

    first, second = get_llm(), get_llm()

    assert first is second
    assert isinstance(first, AnthropicLLM)


def test_the_real_sdk_sends_a_structured_output_request() -> None:
    """Runs the actual Anthropic SDK end to end, with the network replaced by a
    fake transport, to check the request we send and how the reply is parsed."""
    sent: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(json.loads(request.content))
        answer = PARSED.model_dump_json()
        return httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-haiku-5-5",
                "content": [{"type": "text", "text": answer}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 100, "output_tokens": 40},
            },
        )

    client = anthropic.Anthropic(
        api_key="sk-ant-test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = extract(AnthropicLLM(client, "claude-haiku-5-5"))

    assert result.output == PARSED
    assert sent["model"] == "claude-haiku-5-5"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert "skills" in sent["output_config"]["format"]["schema"]["properties"]
