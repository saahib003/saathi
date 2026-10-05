# Gemini Client — Phase 2

## What exists

The Gemini boundary is implemented in `backend/llm/`:

- `client.py` defines the provider-neutral asynchronous `LLMClient` interface.
- `schemas.py` defines `LLMRequest`, `LLMResponse`, and `ToolCall`.
- `gemini_client.py` adapts the official `google-genai` SDK.
- `fake_client.py` provides scripted responses for tests and later agent-loop tests.
- `errors.py` maps configuration, transient, and request failures to application-level exceptions.

Only `backend/llm/gemini_client.py` imports `google.genai`. The rest of the application can use the interface without knowing which provider is installed.

## Why the Interactions API

The current Google documentation recommends the Interactions API for new projects. A request uses `client.interactions.create(model=..., input=...)`, and the response exposes typed execution steps such as `function_call` plus `output_text` for a final answer.

The SDK is pinned to `google-genai==2.3.0`, the minimum version documented for the Interactions API at implementation time. The model name is read only from `GEMINI_MODEL`.

## State ownership

`GEMINI_STORE_INTERACTIONS` defaults to `false`. Phase 2 sends a complete `LLMRequest` and does not use `previous_interaction_id`; the future ContextManager will assemble the history the application owns. The request still supports a string or structured list input so later phases can resend context.

This is a deliberate privacy trade-off. Google documents that `store=false` prevents server-side interaction storage and also prevents using `previous_interaction_id`. The application must therefore manage history and token limits itself.

## Function-call boundary

The adapter passes tool declarations through as JSON-compatible dictionaries and parses returned `function_call` steps into provider-neutral `ToolCall` objects. It does not execute functions and does not implement automatic function calling. Tool execution belongs to the future `ToolGateway`.

```text
LLMRequest -> Gemini Interactions API
                    |
                    +-- model output -> LLMResponse(is_final=True)
                    +-- function_call steps -> ToolCall objects
```

## Reliability and errors

- Calls run in a worker thread because the SDK call is synchronous.
- `asyncio.wait_for` enforces `GEMINI_TIMEOUT_SECONDS`.
- Transient failures (timeouts, 408, 429, 5xx) retry up to `AGENT_MAX_RETRIES` with bounded exponential delay.
- Non-transient failures become `LLMRequestError`.
- Configuration failures are detected before a network call.
- Provider exception text is not returned, preventing accidental secret leakage in application errors.

## Authentication and secrets

`GEMINI_API_KEY` is read by backend settings and passed only to the SDK constructor. It is not included in `LLMRequest`, response types, logs, frontend code, or test output. Real Gemini calls are manual smoke tests only; automated tests use `FakeLLMClient` or an injected fake SDK object.

## Manual smoke test

After installing dependencies and setting `GEMINI_API_KEY` and `GEMINI_MODEL`, run `python scripts/gemini_smoke.py`. It constructs `GeminiClient(get_settings())` and makes one real request. This script is intentionally not an automated test and was not run without a configured API key.

## Alternatives

- `generateContent` remains supported, but the specification selected Interactions API for new agentic work.
- Direct SDK imports throughout the application would be shorter initially, but make tests and provider changes harder.
- Server-side state would reduce repeated context, but conflicts with the project's default data-retention decision.

## Study links

- [Gemini Interactions API](https://ai.google.dev/gemini-api/docs/interactions)
- [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Google GenAI Python SDK](https://pypi.org/project/google-genai/)
