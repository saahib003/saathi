"""Application-level errors from the language-model boundary."""


class LLMError(Exception):
    """Base class for errors safe for the agent layer to handle."""


class LLMConfigurationError(LLMError):
    """The client is not configured well enough to make a request."""


class LLMRequestError(LLMError):
    """A non-transient provider or request error occurred."""


class LLMTransientError(LLMError):
    """A request may succeed if retried within the configured bound."""

