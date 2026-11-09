"""BotForge exception taxonomy (botforge-services#10).

One import for every failure type of the platform. The hierarchy is
typed (the class is the category), the ``code`` rides logs/audits,
the ``user_key`` selects the i18n answer, and the context carries
serializable data only (ADR-0019 rule 3 — no platform objects across
seams).
"""

from botforge.core.exceptions.base import (
    BotforgeError,
    ConfigurationError,
    ErrorContext,
    NotFoundError,
    PermissionError,
    RateLimitError,
    ValidationError,
)
from botforge.core.exceptions.database import (
    ConnectionError,
    DatabaseError,
    DuplicateKeyError,
    QueryError,
)
from botforge.core.exceptions.handlers import ExceptionHandler
from botforge.core.exceptions.platform import (
    ChannelNotFoundError,
    MessageSendError,
    PlatformError,
    PlatformNotSupportedError,
    UserNotFoundError,
)
from botforge.core.exceptions.workflow import (
    InvalidWorkflowStepError,
    WorkflowAlreadyCompletedError,
    WorkflowError,
    WorkflowNotFoundError,
    WorkflowTimeoutError,
)

__all__ = [
    "BotforgeError",
    "ChannelNotFoundError",
    "ConfigurationError",
    "ConnectionError",
    "DatabaseError",
    "DuplicateKeyError",
    "ErrorContext",
    "ExceptionHandler",
    "InvalidWorkflowStepError",
    "MessageSendError",
    "NotFoundError",
    "PermissionError",
    "PlatformError",
    "PlatformNotSupportedError",
    "QueryError",
    "RateLimitError",
    "UserNotFoundError",
    "ValidationError",
    "WorkflowAlreadyCompletedError",
    "WorkflowError",
    "WorkflowNotFoundError",
    "WorkflowTimeoutError",
]
