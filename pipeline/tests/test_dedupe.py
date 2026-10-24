from airadar.dedupe import DedupeIndex
from airadar.normalize import canonical_url, normalize_title, sha256


def _row(did, title, url, chash=None):
    cu = canonical_url(url)
    return {"id": did, "url_hash": sha256(cu), "content_hash": chash, "normalized_title": normalize_title(title),
            "canonical_url": cu, "first_discovered_at": None}


def _m(idx, title, url, chash=None):
    cu = canonical_url(url)
    return idx.match(sha256(cu), chash, normalize_title(title), cu)


def test_same_url_with_tracking_params_is_duplicate():
    idx = DedupeIndex([_row("a", "OpenAI releases new model for developers", "https://openai.com/x")])
    m = _m(idx, "Different headline", "https://www.openai.com/x/?utm_source=hn")
    assert m and m.discovery_id == "a" and m.reason == "url"


def test_near_identical_title_on_other_site_merges():
    idx = DedupeIndex([_row("a", "Google announces Gemini integration for Workspace admins", "https://blog.google/x")])
    m = _m(idx, "Google announces Gemini integration for Workspace admins.", "https://techcrunch.com/y")
    assert m and m.reason == "title"


def test_different_versions_are_not_merged():
    idx = DedupeIndex([_row("a", "Acme Assistant 2.1 released with new admin console", "https://acme.com/a")])
    assert _m(idx, "Acme Assistant 2.2 released with new admin console", "https://news.com/b") is None


def test_similar_titles_on_same_aggregator_are_not_merged():
    idx = DedupeIndex([_row("a", "example/agent-toolkit: a toolkit for building agents", "https://github.com/example/agent-toolkit")])
    assert _m(idx, "example/agent-toolkits: a toolkit for building agents", "https://github.com/example/agent-toolkits") is None


def test_short_titles_never_fuzzy_merge():
    idx = DedupeIndex([_row("a", "AI news today", "https://a.com/1")])
    assert _m(idx, "AI news today!", "https://b.com/2") is None


def test_content_hash_match():
    idx = DedupeIndex([_row("a", "Title one about something long enough", "https://a.com/1", chash="h1")])
    m = _m(idx, "Completely different title text here", "https://b.com/2", chash="h1")
    assert m and m.reason == "content_hash"
