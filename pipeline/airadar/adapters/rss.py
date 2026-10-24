"""RSS / Atom feeds (official blogs, release notes, press)."""
from __future__ import annotations

import feedparser

from ..models import RawItem, Source
from ..normalize import clean_text, parse_datetime
from . import Context


def fetch(source: Source, ctx: Context) -> list[RawItem]:
    url = source.config["url"]
    resp = ctx.http.get(url, headers={"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9"})
    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"unparseable feed: {type(feed.bozo_exception).__name__}")
    limit = int(source.config.get("max_items", 30))
    items: list[RawItem] = []
    for entry in feed.entries[:limit]:
        link = entry.get("link") or ""
        title = clean_text(entry.get("title"), 400)
        if not link or not title:
            continue
        body = ""
        if entry.get("content"):
            body = entry["content"][0].get("value", "")
        body = body or entry.get("summary") or entry.get("description") or ""
        items.append(RawItem(
            source_id=source.id,
            title=title,
            url=link,
            excerpt=clean_text(body, 3000),
            published_at=parse_datetime(entry.get("published_parsed") or entry.get("published")),
            updated_at_source=parse_datetime((entry["updated_parsed"] if "updated_parsed" in entry else None) or entry.get("updated")),
            external_id=entry.get("id") or entry.get("guid"),
            author=entry.get("author"),
            extra={"feed_tags": [t.get("term") for t in entry.get("tags", []) if t.get("term")][:10]},
        ))
    return items
