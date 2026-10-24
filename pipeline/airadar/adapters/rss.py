"""RSS / Atom feeds (official blogs, release notes, press)."""
from __future__ import annotations

import re

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
    type_hint = source.config.get("discovery_type")
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
            discovery_type=type_hint,
            extra={"feed_tags": [t.get("term") for t in entry.get("tags", []) if t.get("term")][:10],
                   **_links(body, link)},
        ))
    return items


_A_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{1,40})\s*</a>', re.I)


def _links(html: str, page_url: str) -> dict:
    """Product-launch feeds (e.g. Product Hunt) put 'Discussion' and 'Link' anchors in the entry body.
    Keep them as references: the product's own site and the launch discussion page."""
    out: dict = {}
    for href, label in _A_RE.findall(html or ""):
        href = href.replace("&amp;", "&")
        label = label.strip().lower()
        if label == "link" and href.startswith("http"):
            out["official_url"] = href
        elif label == "discussion" and href.startswith("http"):
            out["discussion_url"] = href
    return out
