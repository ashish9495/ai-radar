"""Hacker News via the public Algolia HN Search API (hn.algolia.com/api)."""
from __future__ import annotations

import re
import time

from ..models import RawItem, Source
from ..normalize import clean_text, parse_datetime
from . import Context

API = "https://hn.algolia.com/api/v1/search_by_date"


def fetch(source: Source, ctx: Context) -> list[RawItem]:
    hours = int(source.config.get("hours", 24))
    min_points = int(source.config.get("min_points", 30))
    since_ts = int(time.time()) - hours * 3600
    seen: set[str] = set()
    items: list[RawItem] = []
    tags = source.config.get("tags", "story")
    type_hint = source.config.get("discovery_type")
    for query in source.config.get("queries", ["AI"]):
        data = ctx.http.get(API, params={
            "query": query, "tags": tags, "hitsPerPage": 30,
            "numericFilters": f"created_at_i>{since_ts},points>={min_points}",
        }).json()
        for hit in data.get("hits", []):
            oid = hit.get("objectID")
            if not oid or oid in seen or not hit.get("title"):
                continue
            seen.add(oid)
            discussion = f"https://news.ycombinator.com/item?id={oid}"
            url = hit.get("url") or discussion
            title = clean_text(hit["title"], 300)
            if tags == "show_hn":
                title = re.sub(r"^show hn\s*[:\-–]\s*", "", title, flags=re.I)
            items.append(RawItem(
                source_id=source.id,
                title=title,
                url=url,
                excerpt=clean_text(hit.get("story_text"), 2000),
                published_at=parse_datetime(hit.get("created_at")),
                external_id=oid,
                discovery_type=type_hint or ("discussion" if url == discussion else None),
                author=hit.get("author"),
                score=hit.get("points"),
                comments=hit.get("num_comments"),
                extra={"discussion_url": discussion, "matched_query": query},
            ))
    return items
