from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class RawItem:
    """One item as reported by one source, before normalization/dedup."""
    source_id: str
    title: str
    url: str
    excerpt: str = ""
    published_at: datetime | None = None
    released_at: datetime | None = None
    updated_at_source: datetime | None = None
    external_id: str | None = None
    discovery_type: str | None = None   # adapter hint
    author: str | None = None
    score: int | None = None            # HN points, Reddit score, likes...
    comments: int | None = None
    stars: int | None = None
    license: str | None = None
    is_open_source: bool | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Source:
    id: str
    name: str
    adapter: str
    config: dict[str, Any]
    reliability: int = 3
    is_official: bool = False
    enabled: bool = True
    interval_minutes: int = 60
    default_category: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Source":
        return cls(**{k: row[k] for k in cls.__dataclass_fields__ if k in row})


@dataclass
class Category:
    slug: str
    name: str
    priority: int
    keywords: list[str]
    enabled: bool = True

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Category":
        return cls(**{k: row[k] for k in cls.__dataclass_fields__ if k in row})
