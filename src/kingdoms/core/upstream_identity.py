"""Project identification for outbound provider requests (#277).

Every provider adapter that talks to an external upstream identifies
itself: a custom User-Agent naming the project (and, when configured,
a contact address) — never the library default
(``python-httpx/…``, ``websockets/…``). An upstream must be able to
tell who consumes its API; the Liquipedia terms make it mandatory,
every other upstream deserves the same courtesy.

The contact part reuses ``LIQUIPEDIA_CONTACT`` (the operational
contact address is a project-wide fact, not a per-upstream one);
``PROVIDER_CONTACT`` overrides it when an org wants a distinct
address for the non-Liquipedia providers.
"""

from __future__ import annotations

import os

_PROJECT_URL = "https://github.com/merlin-pinpin-org/kingdoms"


def project_user_agent() -> str:
    """Return the identifying User-Agent for outbound provider requests."""
    contact = os.environ.get("PROVIDER_CONTACT", "").strip() or os.environ.get("LIQUIPEDIA_CONTACT", "").strip()
    if contact:
        return f"kingdoms-bot/1.0 ({_PROJECT_URL}; {contact})"
    return f"kingdoms-bot/1.0 ({_PROJECT_URL})"
