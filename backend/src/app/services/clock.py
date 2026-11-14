from datetime import UTC, datetime, timedelta


def now() -> datetime:
    return datetime.now(UTC)


def touch(previous: datetime) -> datetime:
    """A new `updated_at` that is always strictly later than the previous one."""
    return max(now(), previous + timedelta(microseconds=1))
