"""Upstream identification — unit tests (#277).

Every provider adapter that talks to an external upstream must send
the project's identifying User-Agent, never the library default.
"""

from __future__ import annotations

import httpx
import pytest

from botforge.core.upstream_identity import project_user_agent


def test_user_agent_names_the_project() -> None:
    ua = project_user_agent()
    assert ua.startswith("botforge-bot/1.0 (")
    assert "github.com/jj-guild/botforge" in ua
    assert ua.endswith(")")


def test_user_agent_carries_the_contact_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROVIDER_CONTACT", "ops@example.com")
    ua = project_user_agent()
    assert "ops@example.com" in ua


def test_provider_contact_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    from botforge.core.upstream_identity import provider_contact

    monkeypatch.setenv("PROVIDER_CONTACT", " generic@example.com ")
    assert provider_contact() == "generic@example.com"  # trimmed


def test_user_agent_without_contact_carries_no_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROVIDER_CONTACT", raising=False)
    ua = project_user_agent()
    assert "@" not in ua
    assert ua.startswith("botforge-bot/1.0 (")


async def test_librematch_sends_identified_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.headers.get("User-Agent", "")))
        return httpx.Response(200, json=[])

    from botforge.ext_librematch.adapter import LibrematchAdapter

    adapter = LibrematchAdapter(transport=httpx.MockTransport(handler))
    await adapter.fetch_lobbies()
    assert seen and seen[0].startswith("botforge-bot/1.0 (")


def test_techtree_api_headers_identify() -> None:
    from botforge.ext_aoe2techtree.source import ApiContentSource

    source = ApiContentSource("https://example.test/api", api_key="k")
    headers = source._headers()
    assert headers["User-Agent"].startswith("botforge-bot/1.0 (")
    assert headers["authorization"] == "Bearer k"
