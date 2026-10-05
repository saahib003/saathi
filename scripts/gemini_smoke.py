"""Manual, real-network Gemini smoke test for Phase 2.

Run only when GEMINI_API_KEY and GEMINI_MODEL are configured in the environment.
This is intentionally not part of the automated test suite.
"""

import asyncio

from backend.config import get_settings
from backend.llm.gemini_client import GeminiClient
from backend.llm.schemas import LLMRequest


async def main() -> None:
    settings = get_settings()
    client = GeminiClient(settings)
    response = await client.generate(LLMRequest(input="Reply with exactly: Gemini smoke test passed."))
    print(response.text or response.tool_calls)


if __name__ == "__main__":
    asyncio.run(main())

