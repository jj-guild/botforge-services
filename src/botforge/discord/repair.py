"""The repair report: one SDK object that speaks the repair's own story.

A repair is ANY reconcile pass (owner 2026-11-26: "fais le pour tous
les repair, niveau sdk"): the tree-ensure provisioning, the pins and
roles, the forum syncs, the matches forum's seed. The lesson engraved
this week: a SILENT repair reads like an eternity that did nothing -
every phase announces itself, every phase carries its count, the
finish speaks the duration.

Usage::

    with repair(logger, "matches forum", subject=guild_id) as rep:
        rep.step("ensure posts", created=1, dead=0)
        rep.step("post cards", cards=17)
    # -> INFO matches forum REPAIR (guild X): ensure posts (created=1, dead=0)
    # -> INFO matches forum REPAIR (guild X): post cards (cards=17)
    # -> INFO matches forum REPAIR (guild X): DONE in 12.3s (cards=17, created=1)
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from logging import Logger
from typing import Any


class RepairReport:
    """One repair's progress: steps with counts, a finish with the duration."""

    def __init__(
        self,
        logger: Logger,
        name: str,
        subject: str = "",
        progress: Callable[[str, RepairReport], None] | None = None,
    ) -> None:
        self._logger = logger
        self._name = str(name)
        self._subject = str(subject)
        self._started_at = time.time()
        self._totals: dict[str, int] = {}
        # the user-facing plan mirror (owner 2026-11-26: "ne dit pas
        # que ça travaille") - a SYNC callable receiving the line AND
        # the report (the view builder reads the steps): the caller
        # schedules its own async delivery (a message edit, a task)
        self._progress = progress
        # the step ledger (the plan view reads this)
        self.steps: list[str] = []
        # the DONE line (set by done(); the view's synthèse reads it)
        self.finished: str = ""

    @property
    def tag(self) -> str:
        """The log prefix: the repair's own name (and its subject)."""
        return f"{self._name} REPAIR" + (f" ({self._subject})" if self._subject else "")

    def step(self, message: str, display: str = "", **counts: int) -> None:
        """Announce one phase with its own counts (INFO, always).

        ``display`` is the USER-facing sentence (owner 2026-11-26:
        "trop technique et pas traduit") - a localized, human line; the
        log keeps its own terse technical line. The view renders the
        display, the logs keep the tag.
        """
        for key, value in counts.items():
            self._totals[key] = self._totals.get(key, 0) + int(value)
        if counts:
            joined = ", ".join(f"{key}={value}" for key, value in counts.items())
            line = f"{self.tag}: {message} ({joined})"
        else:
            line = f"{self.tag}: {message}"
        self._logger.info(line)
        self.steps.append(display or line)
        if self._progress is not None:
            try:
                self._progress(display or line, self)
            except Exception:  # noqa: S110 - the mirror never kills the repair
                pass

    @contextmanager
    def phase(self, label: str, **counts: int) -> Iterator[RepairReport]:
        """One timed phase: the step at the entry, the duration at the exit."""
        self.step(label, display=label, **counts)
        phase_started = time.time()
        try:
            yield self
        finally:
            self._logger.info(
                "%s: %s done in %.1fs", self.tag, label, time.time() - phase_started
            )

    def done(self, message: str = "DONE", **counts: int) -> None:
        """Finish the repair: the duration and the accumulated counts."""
        for key, value in counts.items():
            self._totals[key] = self._totals.get(key, 0) + int(value)
        totals = (
            " (" + ", ".join(f"{key}={value}" for key, value in self._totals.items()) + ")"
            if self._totals
            else ""
        )
        line = f"{self.tag}: {message} in {time.time() - self._started_at:.1f}s{totals}"
        self._logger.info(line)
        self.steps.append(line)
        if self._progress is not None:
            try:
                self._progress(line, self)
            except Exception:  # noqa: S110 - the mirror never kills the repair
                pass


@contextmanager
def repair(logger: Logger, name: str, subject: Any = "") -> Iterator[RepairReport]:
    """Open one repair: the report speaks, the ``with`` guarantees the DONE."""
    report = RepairReport(logger, name, str(subject))
    try:
        yield report
    except Exception:
        report.done("FAILED")
        raise
    report.done()
