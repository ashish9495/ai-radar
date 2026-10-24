"""Reddit. Uses the official OAuth API (app-only) when credentials exist, otherwise the public RSS feed.

Reddit frequently blocks unauthenticated requests from cloud IP ranges such as GitHub Actions,
so RSS-only mode is best effort and failures surface in source health.
"""
from __future__ import annotations

import feedparser

from ..models import RawItem, Source
from ..normalize import clean_text, parse_datetime
from . import Context

_token_cache: dict[str, str] = {}


def _oauth_token(ctx: Context) -> str:
    if "token" in _token_cache:
        return _token_cache["token"]
    resp = ctx.http.request("POST", "https://www.reddit.com/api/v1/access_token",
                            data={"grant_type": "client_credentials"},
                            auth=(ctx.config.reddit_client_id, ctx.config.reddit_client_secret))
    token = resp.json()["access_token"]
    _token_cache["token"] = token
    return token


def fetch(source: Source, ctx: Context) -> list[RawItem]:
    sub = source.config["subreddit"]
    listing = source.config.get("listing", "top")
    t = source.config.get("t", "day")
    limit = int(source.config.get("limit", 25))
    if ctx.config.reddit_client_id and ctx.config.reddit_client_secret:
        token = _oauth_token(ctx)
        data = ctx.http.get(f"https://oauth.reddit.com/r/{sub}/{listing}",
                            params={"t": t, "limit": limit, "raw_json": 1},
                            headers={"Authorization": f"Bearer {token}"}).json()
        items = []
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            if p.get("stickied") or p.get("over_18"):
                continue
            permalink = f"https://www.reddit.com{p.get('permalink', '')}"
            url = p.get("url_overridden_by_dest") or permalink
            items.append(RawItem(
                source_id=source.id, title=clean_text(p.get("title"), 300), url=url,
                excerpt=clean_text(p.get("selftext"), 2000),
                published_at=parse_datetime(p.get("created_utc")), external_id=p.get("name"),
                discovery_type="discussion" if url == permalink else None,
                author=p.get("author"), score=p.get("score"), comments=p.get("num_comments"),
                extra={"discussion_url": permalink, "subreddit": sub, "flair": p.get("link_flair_text")},
            ))
        return items

    resp = ctx.http.get(f"https://www.reddit.com/r/{sub}/{listing}/.rss", params={"t": t, "limit": limit})
    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        raise ValueError("unparseable reddit feed")
    return [RawItem(
        source_id=source.id, title=clean_text(e.get("title"), 300), url=e.get("link"),
        excerpt=clean_text((e.get("content") or [{}])[0].get("value") or e.get("summary"), 2000),
        published_at=parse_datetime(e.get("published_parsed") or (e["updated_parsed"] if "updated_parsed" in e else None)),
        external_id=e.get("id"), discovery_type="discussion", author=e.get("author"),
        extra={"discussion_url": e.get("link"), "subreddit": sub},
    ) for e in feed.entries[:limit] if e.get("link") and e.get("title")]
