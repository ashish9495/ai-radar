"""Duplicate detection. Conservative by design: we prefer a missed merge over merging two
different announcements that merely have similar headlines."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from .normalize import registered_domain, version_tokens

TITLE_THRESHOLD = 0.93
WINDOW = timedelta(days=4)


@dataclass
class Match:
    discovery_id: str
    reason: str          # url | content_hash | title
    similarity: float = 1.0


class DedupeIndex:
    def __init__(self, rows: list[dict]):
        self.by_url: dict[str, str] = {}
        self.by_content: dict[str, str] = {}
        self.titles: list[tuple[str, str, str, datetime, frozenset[str]]] = []
        for r in rows:
            self.add(r["id"], r["url_hash"], r.get("content_hash"), r["normalized_title"], r["canonical_url"],
                     _dt(r.get("first_discovered_at")))

    def add(self, did: str, url_hash: str, chash: str | None, ntitle: str, url: str, when: datetime | None = None):
        self.by_url[url_hash] = did
        if chash:
            self.by_content.setdefault(chash, did)
        self.titles.append((did, ntitle, registered_domain(url), when or datetime.now(timezone.utc), version_tokens(ntitle)))

    def match(self, url_hash: str, chash: str | None, ntitle: str, url: str) -> Match | None:
        if url_hash in self.by_url:
            return Match(self.by_url[url_hash], "url")
        if chash and chash in self.by_content:
            return Match(self.by_content[chash], "content_hash")
        if len(ntitle) < 25:  # short titles are too ambiguous to fuzzy-merge
            return None
        now = datetime.now(timezone.utc)
        my_versions = version_tokens(ntitle)
        my_domain = registered_domain(url)
        best: Match | None = None
        for did, other, domain, when, versions in self.titles:
            if now - when > WINDOW or versions != my_versions:
                continue
            # Aggregator domains host many unrelated items; never fuzzy-merge within them.
            if domain == my_domain and domain in {"github.com", "huggingface.co", "arxiv.org", "reddit.com",
                                                   "ycombinator.com", "producthunt.com"}:
                continue
            ratio = SequenceMatcher(None, ntitle, other).ratio()
            if ratio >= TITLE_THRESHOLD and (best is None or ratio > best.similarity):
                best = Match(did, "title", round(ratio, 3))
        return best


def _dt(v) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
