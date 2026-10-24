"""Source adapters. Each adapter turns one configured source into RawItems."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from ..config import Config
from ..http import Http
from ..models import RawItem, Source


class AdapterUnavailable(Exception):
    """Adapter cannot run (e.g. missing optional credentials). Reported as 'skipped', not 'failed'."""


@dataclass
class Context:
    http: Http
    config: Config
    since: datetime | None = None  # last successful collection for this source


AdapterFn = Callable[[Source, Context], list[RawItem]]


def registry() -> dict[str, AdapterFn]:
    from . import arxiv, github, hackernews, huggingface, reddit, rss, web_search
    return {
        "rss": rss.fetch,
        "github_releases": github.fetch_releases,
        "github_search": github.fetch_search,
        "hackernews": hackernews.fetch,
        "reddit": reddit.fetch,
        "huggingface": huggingface.fetch,
        "arxiv": arxiv.fetch,
        "web_search": web_search.fetch,
    }
