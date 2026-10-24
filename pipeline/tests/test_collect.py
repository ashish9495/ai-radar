from datetime import datetime, timedelta, timezone

from airadar import collect
from airadar.models import Source


def test_end_to_end_collection_mocked(store, config, http):
    result = collect.run(store, config, http, force=True)
    s = result["sources"]
    assert s["openai-news"]["status"] == "success"
    assert s["hn-ai"]["status"] == "success"
    assert s["gh-releases"]["status"] == "success"
    assert s["arxiv-ai"]["status"] == "success"
    # A blocked source fails in isolation and is recorded, without crashing the run.
    assert s["reddit-localllama"]["status"] == "failed"
    assert "403" in s["reddit-localllama"]["error"]
    # Unconfigured optional provider is skipped, not failed.
    assert s["web-search"]["status"] == "skipped"
    assert result["status"] == "partial"

    titles = {d["title"] for d in store.discoveries.values()}
    assert "Introducing a new reasoning model for developers" in titles
    assert not any(t == "" for t in titles), "empty-title items must be dropped"
    assert "ollama/ollama v0.12.0" in titles
    assert not any("draft" == t for t in titles)

    # The OpenAI post seen on both the official feed and HN is ONE discovery with TWO sightings.
    oa = [d for d in store.discoveries.values() if d["title"].startswith("Introducing a new reasoning")]
    assert len(oa) == 1
    sightings = {x["source_id"] for x in store.sightings if x["discovery_id"] == oa[0]["id"]}
    assert sightings == {"openai-news", "hn-ai"}
    assert oa[0]["canonical_url"] == "https://openai.com/index/new-reasoning-model"

    undated = next(d for d in store.discoveries.values() if d["title"] == "Item with no date at all")
    assert undated["published_at"] is None

    rel = next(d for d in store.discoveries.values() if d["title"] == "ollama/ollama v0.12.0")
    assert rel["license"] == "MIT" and rel["stars"] == 150000 and rel["released_at"]

    assert store.health["reddit-localllama"]["consecutive_failures"] == 1
    assert store.health["openai-news"]["status"] == "healthy"


def test_rerun_is_idempotent(store, config, http):
    collect.run(store, config, http, force=True)
    n = len(store.discoveries)
    sightings = len(store.sightings)
    second = collect.run(store, config, http, force=True)
    assert len(store.discoveries) == n
    assert len(store.sightings) == sightings
    assert second["items_new"] == 0


def test_interval_respected(store, config, http):
    collect.run(store, config, http, force=True)
    again = collect.run(store, config, http)  # not forced: everything was just attempted
    assert all(v["status"] == "not_due" for v in again["sources"].values())


def test_failing_source_becomes_failing_after_three_attempts(store, config, http):
    for _ in range(3):
        collect.run(store, config, http, only=["reddit-localllama"], force=True)
    assert store.health["reddit-localllama"]["status"] == "failing"


def test_delayed_status():
    src = Source("x", "x", "rss", {}, interval_minutes=30)
    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=5)).isoformat()
    assert collect.health_status(src, {"last_success_at": old, "consecutive_failures": 0}, now) == "delayed"
    assert collect.health_status(src, {"last_success_at": now.isoformat(), "consecutive_failures": 0}, now) == "healthy"


def test_rate_limit_is_reported(store, config, router, http):
    router.routes.insert(0, ("hn.algolia.com", 429, b"slow down", {"retry-after": "1"}))
    result = collect.run(store, config, http, only=["hn-ai"], force=True)
    assert result["sources"]["hn-ai"]["status"] == "failed"
    assert "RateLimited" in result["sources"]["hn-ai"]["error"]


def test_empty_feed_is_success_with_zero_items(store, config, router, http):
    router.routes.insert(0, ("openai.com/news/rss.xml", 200,
                             b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>', {}))
    result = collect.run(store, config, http, only=["openai-news"], force=True)
    assert result["sources"]["openai-news"]["status"] == "success"
    assert result["sources"]["openai-news"]["items_fetched"] == 0


def test_old_backlog_items_are_skipped(store, config, router, http):
    old = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>An article from months ago about AI agents</title><link>https://openai.com/index/old</link><pubDate>Mon, 02 Jun 2025 10:00:00 GMT</pubDate></item>
<item><title>Fresh article about AI agents today</title><link>https://openai.com/index/fresh</link><pubDate>''' + \
        __import__("email.utils").utils.format_datetime(datetime.now(timezone.utc) - timedelta(hours=3)).encode() + b'''</pubDate></item>
</channel></rss>'''
    router.routes.insert(0, ("openai.com/news/rss.xml", 200, old, {}))
    result = collect.run(store, config, http, only=["openai-news"], force=True)
    titles = {d["title"] for d in store.discoveries.values()}
    assert "Fresh article about AI agents today" in titles
    assert "An article from months ago about AI agents" not in titles
    assert result["items_too_old"] == 1


def test_product_hunt_links_and_show_hn_tools(store, config, router, http, sources):
    from airadar.models import Source
    ph = b'''<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>PH</title>
<entry><id>tag:ph,2005:Post/1</id><published>''' + datetime.now(timezone.utc).isoformat().encode() + b'''</published>
<link rel="alternate" type="text/html" href="https://www.producthunt.com/products/agentx"/><title>AgentX</title>
<content type="html">&lt;p&gt;AI agent for helpdesk tickets&lt;/p&gt;&lt;p&gt;&lt;a href="https://www.producthunt.com/products/agentx?utm_campaign=x"&gt;Discussion&lt;/a&gt; | &lt;a href="https://www.producthunt.com/r/p/1?app_id=339"&gt;Link&lt;/a&gt;&lt;/p&gt;</content></entry></feed>'''
    router.routes.insert(0, ("producthunt.com/feed", 200, ph, {}))
    store.sources += [
        Source("producthunt-ai", "PH AI", "rss", {"url": "https://www.producthunt.com/feed?category=artificial-intelligence", "discovery_type": "tool"}, 2, False, True, 15, "daily-tools"),
        Source("hn-show-ai", "Show HN AI", "hackernews", {"tags": "show_hn", "queries": ["AI"], "min_points": 1, "discovery_type": "tool"}, 2, False, True, 15, "daily-tools"),
    ]
    collect.run(store, config, http, only=["producthunt-ai", "hn-show-ai"], force=True)
    agentx = next(d for d in store.discoveries.values() if d["title"] == "AgentX")
    assert agentx["discovery_type"] == "tool"
    meta = next(s["raw_meta"] for s in store.sightings if s["discovery_id"] == agentx["id"])
    assert meta["official_url"] == "https://www.producthunt.com/r/p/1?app_id=339"
    assert meta["discussion_url"].startswith("https://www.producthunt.com/products/agentx")
    shown = [d for d in store.discoveries.values() if "ServiceNow" in d["title"]]
    assert shown and not shown[0]["title"].lower().startswith("show hn") and shown[0]["discovery_type"] == "tool"
