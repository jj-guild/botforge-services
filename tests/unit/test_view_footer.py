"""The view-id guardrails: build_view foots, require_declared rejects."""

import pytest


def test_build_view_appends_the_id_footer() -> None:
    """build_view carries the id as the LAST item — the only way to build."""
    import discord

    from botforge.discord.ui.view_footer import build_view

    view = build_view("panel:game:aoe2:live", discord.ui.TextDisplay("body"))
    comps = view.to_components()
    assert len(comps) == 2  # the body + the id line
    assert "panel:game:aoe2:live" in comps[-1]["content"]


def test_require_declared_view_id_rejects_unknown() -> None:
    """An undeclared id fails fast, not as a dead button."""
    from botforge.discord.ui.view_footer import require_declared_view_id

    with pytest.raises(ValueError, match="not declared"):
        require_declared_view_id("panel:game:aoe2:not-declared-anywhere")
