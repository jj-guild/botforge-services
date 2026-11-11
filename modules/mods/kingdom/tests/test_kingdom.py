"""kingdom mod — scaffold acceptance test (MockDiscord, in-memory stores)."""

from __future__ import annotations


def test_kingdom_cog_package_loads() -> None:
    """The generated cog package imports against the core seams."""
    from botforge.mods.kingdom import cogs  # noqa: F401


def test_kingdom_service_implements_the_contract() -> None:
    """The service package exposes the contract's implementation."""
    from botforge.mods.kingdom.grpc import KingdomServiceImpl
    from botforge.mods.kingdom.grpc.contract import KingdomService

    impl = KingdomServiceImpl()
    assert isinstance(impl, KingdomService)
