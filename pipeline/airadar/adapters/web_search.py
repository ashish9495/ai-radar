"""Configurable web search (Brave Search API or Exa). Disabled unless SEARCH_PROVIDER + SEARCH_API_KEY are set."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..models import RawItem, Source
from ..normalize import clean_text, parse_datetime
from . import AdapterUnavailable, Context


def _brave(ctx: Context, query: str, days: int, n: int) -> list[dict]:
    freshness = "pd" if days <= 1 else "pw" if days <= 7 else "pm"
    data = ctx.http.get("https://api.search.brave.com/res/v1/web/search",
                        params={"q": query, "count": n, "freshness": freshness},
                        headers={"X-Subscription-Token": ctx.config.search_api_key, "Accept": "application/json"}).json()
    return [{"title": r.get("title"), "url": r.get("url"), "text": r.get("description"),
             "published": r.get("page_age")} for r in data.get("web", {}).get("results", [])]


def _exa(ctx: Context, query: str, days: int, n: int) -> list[dict]:
    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    data = ctx.http.request("POST", "https://api.exa.ai/search",
                            json={"query": query, "numResults": n, "startPublishedDate": start,
                                  "contents": {"text": {"maxCharacters": 1500}}},
                            headers={"x-api-key": ctx.config.search_api_key}).json()
    return [{"title": r.get("title"), "url": r.get("url"), "text": r.get("text"),
             "published": r.get("publishedDate")} for r in data.get("results", [])]


PROVIDERS = {"brave": _brave, "exa": _exa}


def fetch(source: Source, ctx: Context) -> list[RawItem]:
    provider = PROVIDERS.get(ctx.config.search_provider)
    if not provider or not ctx.config.search_api_key:
        raise AdapterUnavailable("web search not configured (set SEARCH_PROVIDER and SEARCH_API_KEY)")
    days = int(source.config.get("freshness_days", 2))
    n = int(source.config.get("per_query", 8))
    items: list[RawItem] = []
    for q in source.config.get("queries", []):
        for r in provider(ctx, q, days, n):
            if not r.get("url") or not r.get("title"):
                continue
            items.append(RawItem(
                source_id=source.id, title=clean_text(r["title"], 300), url=r["url"],
                excerpt=clean_text(r.get("text"), 2000), published_at=parse_datetime(r.get("published")),
                extra={"search_query": q, "search_provider": ctx.config.search_provider},
            ))
    return items
