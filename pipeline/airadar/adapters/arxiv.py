"""arXiv API (Atom). Preprints — not peer reviewed."""
from __future__ import annotations

import feedparser

from ..models import RawItem, Source
from ..normalize import clean_text, parse_datetime
from . import Context

API = "https://export.arxiv.org/api/query"


def fetch(source: Source, ctx: Context) -> list[RawItem]:
    resp = ctx.http.get(API, params={
        "search_query": source.config.get("query", "cat:cs.AI"),
        "sortBy": "submittedDate", "sortOrder": "descending",
        "max_results": int(source.config.get("max_results", 30)),
    })
    feed = feedparser.parse(resp.content)
    items = []
    for e in feed.entries:
        link = next((lk["href"] for lk in e.get("links", []) if lk.get("type") == "text/html"), e.get("link"))
        if not link:
            continue
        items.append(RawItem(
            source_id=source.id,
            title=clean_text(e.get("title"), 400),
            url=link,
            excerpt=clean_text(e.get("summary"), 3000),
            published_at=parse_datetime(e.get("published_parsed") or e.get("published")),
            updated_at_source=parse_datetime((e["updated_parsed"] if "updated_parsed" in e else None) or e.get("updated")),
            external_id=e.get("id"),
            discovery_type="paper",
            author=", ".join(a.get("name", "") for a in e.get("authors", [])[:5]),
            extra={"categories": [t.get("term") for t in e.get("tags", [])][:6], "peer_reviewed": False},
        ))
    return items
