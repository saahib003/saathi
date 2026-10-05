import asyncio
from types import SimpleNamespace

import pytest

from backend.config import Settings
from backend.llm.errors import LLMConfigurationError, LLMRequestError
from backend.llm.fake_client import FakeLLMClient
from backend.llm.gemini_client import GeminiClient
from backend.llm.schemas import LLMRequest, LLMResponse, ToolCall


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "gemini_api_key": "test-key",
        "gemini_model": "gemini-test-model",
        "gemini_timeout_seconds": 2,
        "agent_max_retries": 2,
    }
    values.update(overrides)
    return Settings(**values)


def test_fake_client_returns_scripted_response_and_records_request() -> None:
    expected = LLMResponse(is_final=True, text="hello")
    client = FakeLLMClient([expected])
    request = LLMRequest(input="Hi")

    assert asyncio.run(client.generate(request)) == expected
    assert client.requests == [request]


def test_gemini_client_requires_key_and_model() -> None:
    with pytest.raises(LLMConfigurationError):
        GeminiClient(Settings(gemini_api_key="", gemini_model="model"))
    with pytest.raises(LLMConfigurationError):
        GeminiClient(Settings(gemini_api_key="key", gemini_model=""))


def test_gemini_client_maps_final_output_and_function_calls() -> None:
    response = SimpleNamespace(
        id="interaction-1",
        output_text="",
        steps=[SimpleNamespace(type="function_call", id="call-1", name="lookup", arguments={"q": "x"})],
    )

    class FakeInteractions:
        def create(self, **payload: object) -> SimpleNamespace:
            assert payload["model"] == "gemini-test-model"
            assert payload["store"] is False
            assert payload["input"] == "Find x"
            return response

    client = GeminiClient(settings(), sdk_client=SimpleNamespace(interactions=FakeInteractions()))
    result = asyncio.run(client.generate(LLMRequest(input="Find x")))

    assert result.is_final is False
    assert result.tool_calls == [ToolCall(id="call-1", name="lookup", arguments={"q": "x"})]
    assert result.provider_response_id == "interaction-1"


def test_gemini_client_retries_transient_failure() -> None:
    attempts = 0
    sleeps: list[float] = []

    class TemporaryError(Exception):
        status_code = 503

    class FakeInteractions:
        def create(self, **_: object) -> SimpleNamespace:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise TemporaryError()
            return SimpleNamespace(id="ok", output_text="done", steps=[])

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    client = GeminiClient(
        settings(agent_max_retries=1),
        sdk_client=SimpleNamespace(interactions=FakeInteractions()),
        sleep=fake_sleep,
    )
    result = asyncio.run(client.generate(LLMRequest(input="retry")))

    assert result.text == "done"
    assert attempts == 2
    assert sleeps == [1]


def test_gemini_client_does_not_retry_non_transient_error() -> None:
    class BadRequest(Exception):
        status_code = 400

    class FakeInteractions:
        def create(self, **_: object) -> None:
            raise BadRequest("private-key-value")

    client = GeminiClient(settings(), sdk_client=SimpleNamespace(interactions=FakeInteractions()))
    with pytest.raises(LLMRequestError) as caught:
        asyncio.run(client.generate(LLMRequest(input="bad")))
    assert "private-key-value" not in str(caught.value)
