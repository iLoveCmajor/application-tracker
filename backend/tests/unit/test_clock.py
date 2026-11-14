from datetime import UTC, datetime, timedelta

from app.services.clock import now, touch


def test_now_is_timezone_aware_utc() -> None:
    assert now().tzinfo == UTC


def test_touch_is_strictly_later_even_when_the_clock_is_behind() -> None:
    future = datetime.now(UTC) + timedelta(hours=1)
    assert touch(future) == future + timedelta(microseconds=1)


def test_touch_uses_the_current_time_when_it_is_later() -> None:
    past = datetime(2026, 1, 1, tzinfo=UTC)
    assert touch(past) > past + timedelta(days=1)
