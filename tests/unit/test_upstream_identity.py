"""Upstream identification — unit tests (#277).

Every provider adapter that talks to an external upstream must send
the project's identifying User-Agent, never the library default.
"""

from __future__ import annotations

import httpx
import pytest

from kingdoms.core.upstream_identity import project_user_agent


def test_user_agent_names_the_project() -> None:
    ua = project_user_agent()
    assert ua.startswith("kingdoms-bot/1.0 (")
    assert "github.com/merlin-pinpin-org/kingdoms" in ua
    assert ua.endswith(")")


def test_user_agent_carries_the_contact_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROVIDER_CONTACT", "ops@example.com")
    monkeypatch.delenv("LIQUIPEDIA_CONTACT", raising=False)
    ua = project_user_agent()
    assert "ops@example.com" in ua


def test_liquipedia_contact_is_the_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROVIDER_CONTACT", raising=False)
    monkeypatch.setenv("LIQUIPEDIA_CONTACT", "legacy@example.com")
    assert "legacy@example.com" in project_user_agent()


def test_provider_contact_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    from kingdoms.core.upstream_identity import provider_contact

    monkeypatch.setenv("PROVIDER_CONTACT", " generic@example.com ")
    monkeypatch.setenv("LIQUIPEDIA_CONTACT", "other@example.com")
    assert provider_contact() == "generic@example.com"  # trimmed, generic first


def test_provider_contact_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIQUIPEDIA_CONTACT", "ops@example.com")
    monkeypatch.setenv("PROVIDER_CONTACT", "dev@example.org")
    assert "dev@example.org" in project_user_agent()
    assert "ops@example.com" not in project_user_agent()


async def test_librematch_sends_identified_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.headers.get("User-Agent", "")))
        return httpx.Response(200, json=[])

    from kingdoms.ext_librematch.adapter import LibrematchAdapter

    adapter = LibrematchAdapter(transport=httpx.MockTransport(handler))
    await adapter.fetch_lobbies()
    assert seen and seen[0].startswith("kingdoms-bot/1.0 (")


def test_techtree_api_headers_identify() -> None:
    from kingdoms.ext_aoe2techtree.source import ApiContentSource

    source = ApiContentSource("https://example.test/api", api_key="k")
    headers = source._headers()
    assert headers["User-Agent"].startswith("kingdoms-bot/1.0 (")
    assert headers["authorization"] == "Bearer k"
