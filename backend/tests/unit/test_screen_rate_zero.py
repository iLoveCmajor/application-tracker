from app.services.funnel import compute_funnel, screen_rate


def test_screen_rate_is_none_when_nothing_applied() -> None:
    assert screen_rate(0, 0) is None


def test_funnel_without_applications_has_null_rates() -> None:
    funnel = compute_funnel([], [])
    assert all(s.screen_rate is None for s in funnel.by_source)
