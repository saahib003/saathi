"""Gemini Interactions API adapter.

Only this module imports the Google SDK. The rest of the application uses
the provider-neutral types in ``schemas.py``.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from google import genai

from backend.config import Settings
from backend.llm.client import LLMClient
from backend.llm.errors import LLMConfigurationError, LLMRequestError, LLMTransientError
from backend.llm.schemas import LLMRequest, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class GeminiClient(LLMClient):
    """Call Gemini's Interactions API with application-owned history."""

    def __init__(
        self,
        settings: Settings,
        *,
        sdk_client: Any | None = None,
        sleep: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        if not settings.gemini_api_key:
            raise LLMConfigurationError("GEMINI_API_KEY is not configured")
        if not settings.gemini_model:
            raise LLMConfigurationError("GEMINI_MODEL is not configured")
        self.settings = settings
        self._client = sdk_client or genai.Client(api_key=settings.gemini_api_key)
        self._sleep = sleep

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Make a bounded, timeout-protected request and normalize its steps."""
        payload: dict[str, Any] = {
            "model": self.settings.gemini_model,
            "input": request.input,
            "store": self.settings.gemini_store_interactions,
        }
        if request.system_instruction:
            payload["system_instruction"] = request.system_instruction
        if request.tools:
            payload["tools"] = request.tools

        for attempt in range(self.settings.agent_max_retries + 1):
            try:
                raw = await asyncio.wait_for(
                    asyncio.to_thread(self._client.interactions.create, **payload),
                    timeout=self.settings.gemini_timeout_seconds,
                )
                return self._parse_response(raw)
            except asyncio.TimeoutError as exc:
                error: Exception = LLMTransientError("Gemini request timed out")
            except Exception as exc:  # SDK exception classes vary by release.
                error = self._map_error(exc)
                if not isinstance(error, LLMTransientError):
                    raise error from exc

            if attempt >= self.settings.agent_max_retries:
                raise error
            delay = min(2**attempt, 8)
            logger.warning("Transient Gemini request failure; retrying in %ss", delay)
            await self._sleep(delay)

        raise AssertionError("retry loop must return or raise")

    @staticmethod
    def _parse_response(raw: Any) -> LLMResponse:
        calls: list[ToolCall] = []
        for index, step in enumerate(getattr(raw, "steps", []) or []):
            if getattr(step, "type", None) != "function_call":
                continue
            arguments = getattr(step, "arguments", {}) or {}
            if not isinstance(arguments, dict):
                raise LLMRequestError("Gemini returned non-object function arguments")
            calls.append(
                ToolCall(
                    id=str(getattr(step, "id", None) or f"function-call-{index}"),
                    name=str(getattr(step, "name", "")),
                    arguments=arguments,
                )
            )
        output_text = getattr(raw, "output_text", None)
        return LLMResponse(
            is_final=not calls,
            text=output_text if isinstance(output_text, str) else None,
            tool_calls=calls,
            provider_response_id=getattr(raw, "id", None),
        )

    @staticmethod
    def _map_error(error: Exception) -> Exception:
        status = getattr(error, "status_code", None) or getattr(error, "code", None)
        if status == 429 or status in {408, 500, 502, 503, 504}:
            return LLMTransientError("Gemini temporarily unavailable")
        return LLMRequestError("Gemini request failed")

