"""Exception hierarchy used across Prism."""


class PrismError(Exception):
    """Base class for every error Prism raises."""


class ProviderError(PrismError):
    """A provider returned an unexpected response."""

    def __init__(self, message: str, status: int = None, provider: str = None):
        super().__init__(message)
        self.status = status
        self.provider = provider


class RateLimitError(ProviderError):
    """The provider signalled too many requests (HTTP 429)."""


class ServerError(ProviderError):
    """The provider returned a 5xx server error."""


class TimeoutError(PrismError):
    """The transport timed out before a response arrived."""


class CircuitOpenError(PrismError):
    """The circuit breaker is open and rejecting calls."""


class ToolError(PrismError):
    """A tool/function call raised an exception."""


class RetryExhausted(PrismError):
    """All retry attempts failed."""

    def __init__(self, message: str, cause: BaseException = None, attempts: int = 0):
        super().__init__(message)
        self.cause = cause
        self.attempts = attempts
