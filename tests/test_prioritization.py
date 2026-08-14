"""Pure unit tests — no external services, fast, deterministic."""
from backend_v3.advisor.prioritization import STALE_CONTACT_DAYS, TODAY, compute_priority


def test_recent_life_event_yields_high_priority():
    recent_date = TODAY.isoformat()
    result = compute_priority(
        life_events=[{"description": "Something happened", "date": recent_date}],
        concerns=[],
        meetings=[{"date": recent_date}],
    )
    assert result["priority"] == "high"
    assert result["most_recent_life_event"] == "Something happened"


def test_old_last_contact_is_flagged_stale_and_high_priority():
    old_date = "2020-01-01"
    result = compute_priority(life_events=[], concerns=[], meetings=[{"date": old_date}])
    assert result["is_stale"] is True
    assert result["priority"] == "high"
    assert result["days_since_contact"] >= STALE_CONTACT_DAYS


def test_multiple_concerns_yield_at_least_medium_priority():
    result = compute_priority(
        life_events=[], concerns=[{"topic": "a"}, {"topic": "b"}], meetings=[]
    )
    assert result["priority"] in ("high", "medium")
    assert result["open_concerns_count"] == 2


def test_no_signals_yields_low_priority():
    result = compute_priority(life_events=[], concerns=[], meetings=[])
    assert result["priority"] == "low"
    assert result["is_stale"] is False
    assert result["last_contact_date"] is None


def test_missing_dates_do_not_crash():
    result = compute_priority(
        life_events=[{"description": "x", "date": None}],
        concerns=[],
        meetings=[{"date": None}],
    )
    assert result["priority"] in ("high", "medium", "low")
