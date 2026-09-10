from __future__ import annotations

from datetime import UTC, datetime, timedelta

from server.core.activity import active_seconds


def at(seconds: int) -> datetime:
    return datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC) + timedelta(seconds=seconds)


def test_no_events_and_a_single_event_are_zero():
    assert active_seconds([]) == 0
    assert active_seconds([("start", at(0))]) == 0


def test_heartbeats_accumulate_the_gaps_between_them():
    events = [("start", at(0)), ("heartbeat", at(15)), ("heartbeat", at(30))]
    assert active_seconds(events) == 30


def test_a_long_silence_is_capped_instead_of_counted_as_learning():
    # The learner left the tab for ten minutes and came back.
    events = [("start", at(0)), ("heartbeat", at(600))]
    assert active_seconds(events, cap_seconds=30) == 30


def test_pause_closes_the_interval_and_resume_opens_a_new_one():
    events = [
        ("start", at(0)),
        ("pause", at(10)),      # 10s counted
        ("resume", at(300)),    # the 290s away are not counted
        ("heartbeat", at(310)),  # 10s counted
        ("end", at(320)),       # 10s counted
    ]
    assert active_seconds(events) == 30


def test_events_out_of_order_are_sorted_before_counting():
    events = [("heartbeat", at(20)), ("start", at(0)), ("heartbeat", at(10))]
    assert active_seconds(events) == 20
