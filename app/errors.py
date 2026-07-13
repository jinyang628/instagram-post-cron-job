class InstagramError(RuntimeError):
    """Raised when Instagram rejects a publishing request."""


class CaptionGenerationError(RuntimeError):
    """Raised when OpenRouter cannot generate a usable caption."""
