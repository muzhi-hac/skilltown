"""Turn raw activity events into learning time we are willing to defend.

A learner who leaves the tab open is not learning, so a gap between events is
counted only up to `cap_seconds` and only while the attempt is active. Pausing
or ending closes the interval. This deliberately under-counts rather than
inflating time-on-task.
"""

from __future__ import annotations

from datetime import datetime

ACTIVE_KINDS = frozenset({"start", "heartbeat", "resume"})
DEFAULT_CAP_SECONDS = 30


def active_seconds(
    events: list[tuple[str, datetime]], cap_seconds: int = DEFAULT_CAP_SECONDS
) -> int:
    """Sum the active gaps between consecutive events, capping each gap."""
    total = 0.0
    previous: datetime | None = None
    active = False
    for kind, moment in sorted(events, key=lambda item: item[1]):
        if active and previous is not None:
            gap = (moment - previous).total_seconds()
            if gap > 0:
                total += min(gap, cap_seconds)
        active = kind in ACTIVE_KINDS
        previous = moment
    return int(total)
