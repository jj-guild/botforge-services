"""The SDK repair report (owner 2026-11-26: a SILENT repair reads like a dead one)."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from botforge.discord.repair import RepairReport, repair


def _capturing_logger() -> tuple[MagicMock, list[str]]:
    logger = MagicMock(spec=logging.Logger)
    lines: list[str] = []

    def _info(fmt: str, *args: object) -> None:
        lines.append(fmt % args if args else fmt)

    logger.info.side_effect = _info
    return logger, lines


def test_the_steps_speak_and_the_done_carries_the_totals() -> None:
    logger, lines = _capturing_logger()
    report = RepairReport(logger, "players forum seed", subject="42")
    report.step("ensure posts", created=2)
    report.step("posted the window", cards=17, posts=2)
    report.done()
    assert lines[0] == "players forum seed REPAIR (42): ensure posts (created=2)"
    assert "cards=17" in lines[1] and "posts=2" in lines[1]
    assert lines[2].startswith("players forum seed REPAIR (42): DONE in ")
    # the DONE accumulates: created + cards + posts all read in the finish
    assert "created=2" in lines[2] and "cards=17" in lines[2]


def test_the_context_guarantees_a_done_even_on_failure() -> None:
    logger, lines = _capturing_logger()
    try:
        with repair(logger, "tree ensure", subject="7") as report:
            report.step("provision", channels=3)
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    finishes = [line for line in lines if "FAILED" in line]
    assert finishes and finishes[0].startswith("tree ensure REPAIR (7): FAILED in "), (
        "a failed repair finishes with its own verdict"
    )


def test_the_done_line_speaks_when_given_a_display() -> None:
    """The closing line renders the caller's localized sentence (owner
    2026-11-27: the raw "tree ensure REPAIR (guild): the scopes stand
    in 52.7s (channels=6...)" hit the admin's view) - the {duration}
    placeholder receives the elapsed seconds, the log keeps its own
    terse technical line."""
    import logging
    import time as _time

    from botforge.discord.repair import RepairReport

    logger = logging.getLogger("test.repair.done")
    report = RepairReport(logger, "tree ensure", subject="42")
    report._started_at = _time.time() - 52.7  # the elapsed is the contract under test
    report.done(
        "the scopes stand",
        display="✅ Réparation terminée en {duration}s",
        channels=6,
    )
    assert report.steps[-1] == "✅ Réparation terminée en 52.7s", "the view reads WORDS"
    assert report.steps[-1] != "tree ensure REPAIR (42): the scopes stand", "never the raw tag"
    # without a display the technical line keeps its place (the logs' word)
    plain = RepairReport(logger, "seed", subject="42")
    plain.done("DONE")
    assert plain.steps[-1].startswith("seed REPAIR (42): DONE in "), "the SDK default stays"
