from datetime import datetime, timedelta, timezone

from airadar.normalize import canonical_url, normalize_title, parse_datetime, version_tokens


def test_canonical_url_strips_tracking_and_www():
    assert canonical_url("http://www.Example.com/a/b/?utm_source=x&id=2&ref=hn#frag") == "https://example.com/a/b?id=2"
    assert canonical_url("https://youtu.be/abc123") == "https://youtube.com/watch?v=abc123"
    assert canonical_url("https://old.reddit.com/r/x/") == "https://reddit.com/r/x"


def test_query_params_sorted_for_stable_hash():
    assert canonical_url("https://a.com/p?b=2&a=1") == canonical_url("https://a.com/p?a=1&b=2")


def test_normalize_title():
    assert normalize_title("Show HN: <b>My</b> Tool &amp; Thing!") == "my tool thing"


def test_missing_and_implausible_dates_are_none_not_now():
    assert parse_datetime(None) is None
    assert parse_datetime("") is None
    assert parse_datetime("not a date") is None
    assert parse_datetime("1970-01-01T00:00:00Z") is None
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    assert parse_datetime(future) is None


def test_dates_are_utc():
    dt = parse_datetime("2026-10-24T08:00:00+05:30")
    assert dt.tzinfo == timezone.utc and dt.hour == 2 and dt.minute == 30
    assert parse_datetime("Fri, 23 Oct 2026 17:00:00 GMT").hour == 17


def test_version_tokens():
    assert version_tokens("ollama v0.12.0 released") == frozenset({"0.12.0"})
    assert version_tokens("llama 4 70b model") != version_tokens("llama 4 8b model")
