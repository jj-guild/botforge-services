"""Rate-limit monitoring — unit tests (botforge.discord.rate_limit_monitor).

The tap turns discord.py's internal ``discord.http`` 429 warnings into
structured ``botforge.rate_limit`` warnings with the route and the
retry_after (#276, audit point 5): a rate-limited burst must be
measurable, not absorbed silently by the library's retry.
"""

from __future__ import annotations

import logging

import pytest

from botforge.discord.rate_limit_monitor import (
    RATE_LIMIT_HITS,
    install_rate_limit_monitor,
    reset_rate_limit_hits,
)


@pytest.fixture(autouse=True)
def _clean() -> None:
    """Isolate each test's counters."""
    reset_rate_limit_hits()


def _discord_http() -> logging.Logger:
    return logging.getLogger("discord.http")


def _emit(message: str) -> None:
    """Emit one record exactly the way discord.py's http.py does."""
    _discord_http().warning("%s", message)


def test_route_429_is_tapped_with_retry_after(caplog: pytest.LogCaptureFixture) -> None:
    install_rate_limit_monitor()
    with caplog.at_level(logging.WARNING, logger="botforge.rate_limit"):
        _emit(
            "We are being rate limited. PATCH https://discord.com/api/v10/channels/123 "
            "responded with 429. Retrying in 492.68 seconds."
        )
    assert "PATCH" in caplog.text
    assert "492.68" in caplog.text
    assert "1 hits" in caplog.text
    assert RATE_LIMIT_HITS["PATCH https://discord.com/api/v10/channels/123"] == 1


def test_global_429_is_reported_as_global(caplog: pytest.LogCaptureFixture) -> None:
    install_rate_limit_monitor()
    with caplog.at_level(logging.WARNING, logger="botforge.rate_limit"):
        _emit("Global rate limit has been hit. Retrying in 4.20 seconds.")
    assert "GLOBAL" in caplog.text
    assert RATE_LIMIT_HITS["<global>"] == 1


def test_unrelated_warnings_are_not_reemitted(caplog: pytest.LogCaptureFixture) -> None:
    install_rate_limit_monitor()
    with caplog.at_level(logging.WARNING, logger="botforge.rate_limit"):
        _emit("Some unrelated discord.http warning")
    assert not [r for r in caplog.records if r.name == "botforge.rate_limit"]


def test_install_is_idempotent() -> None:
    install_rate_limit_monitor()
    first = getattr(_discord_http(), "_botforge_rate_limit_handler", None)
    install_rate_limit_monitor()
    assert getattr(_discord_http(), "_botforge_rate_limit_handler", None) is first
