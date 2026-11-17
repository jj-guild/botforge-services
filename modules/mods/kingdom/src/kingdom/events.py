"""The Lord's Day window helpers (P4.1 port of vibe/drasah/main).

Only the calendar machinery the attack service needs: the weekly cron
parsing, the schedule timezone, the Lord's Day window (Sunday 23:30 →
Monday 10:00) and its beta/season-aware ``active_lords_day_window``.
The full EventService orchestrator (the weekly cycle redraft) is a
later tranche — these helpers are its (already validated) seam.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from botforge.mods.kingdom.beta_weekend import beta_lords_day_window

if TYPE_CHECKING:  # pragma: no cover — import cycles never at runtime
    from botforge.mods.kingdom.config import KingdomSeasonConfig
    from botforge.mods.kingdom.models import SeasonState

logger = logging.getLogger("kingdom.events")

_CRON_DAYS: dict[str, int] = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
    "SAT": 5,
    "SUN": 6,
}


def _parse_weekly_cron(cron: str) -> tuple[int, int, int]:
    """Parse a weekly ``m h * * DAY`` cron into (minute, hour, weekday).

    Only the weekly shape is supported (the Season II schedules are
    weekly): anything else is a configuration error and fails loudly
    rather than silently skipping the events.
    """
    parts = cron.split()
    if len(parts) != 5 or parts[2] != "*" or parts[3] != "*":
        raise ValueError(f"only weekly crons (m h * * DAY) are supported: {cron!r}")
    day = _CRON_DAYS.get(parts[4].upper())
    if day is None or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError(f"invalid weekly cron: {cron!r}")
    minute, hour = int(parts[0]), int(parts[1])
    if minute > 59 or hour > 23:
        raise ValueError(f"invalid weekly cron time: {cron!r}")
    return minute, hour, day


def _schedule_timezone(config: KingdomSeasonConfig) -> ZoneInfo:
    """Resolve the scheduling timezone, UTC as the safe fallback."""
    try:
        return ZoneInfo(config.events.schedule_timezone)
    except Exception:
        logger.warning(
            "kingdom: unknown schedule timezone %r - falling back to UTC",
            config.events.schedule_timezone,
        )
        return ZoneInfo("UTC")


def cron_slots_between(
    cron: str,
    after: datetime,
    before: datetime,
    tz: ZoneInfo,
) -> list[datetime]:
    """Return every UTC slot of the weekly cron in ``(after, before]``.

    Drasah's cadence rule (2026-10-11): the first switch lands on the
    FIRST calendar occurrence of the cron day after the season start —
    a season started Saturday gets its first cycle the very next
    Sunday 23:30, no full week of dead time.
    """
    minute, hour, weekday = _parse_weekly_cron(cron)
    if after.tzinfo is None:
        after = after.replace(tzinfo=UTC)
    if before.tzinfo is None:
        before = before.replace(tzinfo=UTC)
    slots: list[datetime] = []
    day = after.astimezone(tz).date()
    last = before.astimezone(tz).date()
    while day <= last:
        if day.weekday() == weekday:
            slot = datetime.combine(day, time(hour, minute), tzinfo=tz).astimezone(UTC)
            if after < slot <= before:
                slots.append(slot)
        day += timedelta(days=1)
    return slots




def lords_day_window(
    config: KingdomSeasonConfig,
    now: datetime,
) -> tuple[datetime, datetime] | None:
    """Return the active Lord's Day window around ``now``, if any.

    The window opens at the weekly cycle slot (Sunday 23:30 by default,
    ``events.cycle_cron``) and closes the NEXT day at
    ``events.lords_day_end_hour`` (Monday 10:00) in the schedule
    timezone. Inside the window an attack cannot be PLAYED: the attack
    service uses this helper to block executions while still accepting
    a declaration whose execution lands after the window (Drasah's
    attack-vs-declaration distinction).
    """
    tz = _schedule_timezone(config)
    minute, hour, weekday = _parse_weekly_cron(config.events.cycle_cron)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    local = now.astimezone(tz)
    for back in range(7):
        day = local.date() - timedelta(days=back)
        if day.weekday() != weekday:
            continue
        start = datetime.combine(day, time(hour, minute), tzinfo=tz).astimezone(UTC)
        if start > now:
            continue
        end = datetime.combine(
            day + timedelta(days=1), time(config.events.lords_day_end_hour, 0), tzinfo=tz
        ).astimezone(UTC)
        return (start, end) if now < end else None
    return None




def active_lords_day_window(
    config: KingdomSeasonConfig,
    season: SeasonState,
    now: datetime,
) -> tuple[datetime, datetime] | None:
    """Return the calendar Lord's Day window, suppressed on the end slot.

    Drasah's endcycle rule (2026-10-11): the endcycle's own Sunday is a
    NORMAL switch (budgets, maps, alliances), but the season's LAST
    Sunday carries NO Lord's Day window — the verdict applies at 23:59
    instead. A finished season never reopens a calendar window either.
    The forced test window is handled separately by the attack service.

    beta-weekend-v1: on a beta season the explicit plan REPLACES the
    calendar — each consumed cycle slot opens its short window (2h),
    the crons are ignored.
    """
    if season.beta_name:
        if season.finished:
            return None
        return beta_lords_day_window(season, now)
    if season.finished:
        return None
    window = lords_day_window(config, now)
    if window is None:
        return None
    tz = _schedule_timezone(config)
    # The window's opening slot is the last cycle slot before ``now``
    # (the next one sits a week later, past the window's end); when the
    # season already consumed its ``weeks`` slots the opening slot was
    # the END one — no window before the 23:59 verdict.
    slots = cron_slots_between(config.events.cycle_cron, season.started_at, now, tz)
    if len(slots) >= config.weeks:
        return None
    return window


