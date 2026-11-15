"""The reasons of domain `oracle` (design §3 *Validation and errors*, §6).

The bottom layer names a failure by Oracle's own error code in upper snake case
where the reply carries one, else by the tool's failure; the tool's failures are
the members below, unique in the domain. An Oracle code is open-ended, so it is
not a member: `snake` makes it.
"""

from __future__ import annotations

import enum
import re

DOMAIN = "oracle"


@enum.unique
class OracleReason(enum.Enum):
    """A failure with no Oracle error code, and the registry API's own."""
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    TOOL_MISSING = "TOOL_MISSING"
    TOOL_FAILED = "TOOL_FAILED"
    BAD_OUTPUT = "BAD_OUTPUT"
    THROTTLED = "THROTTLED"
    SERVER_ERROR = "SERVER_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    DENIED = "DENIED"
    MANIFEST_UNKNOWN = "MANIFEST_UNKNOWN"
    NAME_UNKNOWN = "NAME_UNKNOWN"
    AUTH_CONFIG_MISSING = "AUTH_CONFIG_MISSING"


NOT_AUTHORIZED_OR_NOT_FOUND = "NOT_AUTHORIZED_OR_NOT_FOUND"

_WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")


def snake(code: str) -> str:
    """Oracle's `NotAuthorizedOrNotFound` as `NOT_AUTHORIZED_OR_NOT_FOUND`."""
    return "_".join(word.upper() for word in _WORD.findall(code))
