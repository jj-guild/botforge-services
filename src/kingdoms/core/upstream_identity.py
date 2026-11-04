"""Project identification for outbound provider requests (#277).

Every provider adapter that talks to an external upstream identifies
itself: a custom User-Agent naming the project (and, when configured,
a contact address) — never the library default
(``python-httpx/…``, ``websockets/…``). An upstream must be able to
tell who consumes its API; the Liquipedia terms make it mandatory,
every other upstream deserves the same courtesy.

The contact address is a project-wide fact, not a per-upstream one:
``PROVIDER_CONTACT`` is THE one variable every provider reads
(Liquipedia included).
"""

from __future__ import annotations

import os

_PROJECT_URL = "https://github.com/merlin-pinpin-org/kingdoms"


def provider_contact() -> str:
    """Return the operational contact address (``PROVIDER_CONTACT``)."""
    return os.environ.get("PROVIDER_CONTACT", "").strip()


def project_user_agent() -> str:
    """Return the identifying User-Agent for outbound provider requests."""
    contact = provider_contact()
    if contact:
        return f"kingdoms-bot/1.0 ({_PROJECT_URL}; {contact})"
    return f"kingdoms-bot/1.0 ({_PROJECT_URL})"
