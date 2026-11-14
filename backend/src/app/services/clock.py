from datetime import UTC, date, datetime, timedelta


def now() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    """The server's current date in UTC ("today" in the spec)."""
    return now().date()


def touch(previous: datetime) -> datetime:
    """A new `updated_at` that is always strictly later than the previous one."""
    return max(now(), previous + timedelta(microseconds=1))
