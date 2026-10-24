"""Normalization of URLs, titles, timestamps and text."""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "ref", "ref_src", "source", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "si", "s",
    "_hsenc", "_hsmi", "mkt_tok", "cmpid", "ocid",
}
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def canonical_url(url: str) -> str:
    url = url.strip()
    parts = urlsplit(url)
    scheme = "https" if parts.scheme in ("http", "https", "") else parts.scheme
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in ("m.youtube.com", "youtu.be"):
        if host == "youtu.be":
            return f"https://youtube.com/watch?v={parts.path.strip('/')}"
        host = "youtube.com"
    if host == "old.reddit.com":
        host = "reddit.com"
    port = f":{parts.port}" if parts.port and parts.port not in (80, 443) else ""
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if len(path) > 1:
        path = path.rstrip("/")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False)
             if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")]
    query.sort()
    return urlunsplit((scheme, host + port, path, urlencode(query), ""))


def registered_domain(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "ac", "gov") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def clean_text(text: str | None, limit: int = 4000) -> str:
    text = strip_html(text)
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\t")
    return text[:limit]


def normalize_title(title: str) -> str:
    t = unicodedata.normalize("NFKC", strip_html(title)).lower()
    t = re.sub(r"^(show hn|ask hn|launch hn|tell hn)\s*[:\-]\s*", "", t)
    t = re.sub(r"\s*[\|\-–—]\s*(the verge|techcrunch|hacker news|reddit)$", "", t)
    t = re.sub(r"[^\w\s.\-]", " ", t)
    return _WS_RE.sub(" ", t).strip()


def content_hash(text: str | None) -> str | None:
    body = normalize_title(text or "")
    return sha256(body) if len(body) >= 80 else None


_VERSION_RE = re.compile(r"\b(?:v?\d+(?:\.\d+)+[a-z0-9\-]*|\d+[bkm]\b|\d{2,})", re.I)


def version_tokens(title: str) -> frozenset[str]:
    """Numbers/versions in a title; two items whose version tokens differ are different announcements."""
    return frozenset(m.group(0).lower().lstrip("v") for m in _VERSION_RE.finditer(title))


def parse_datetime(value) -> datetime | None:
    """Parse a timestamp to aware UTC. Returns None (never 'now') if unknown or implausible."""
    if value is None or value == "":
        return None
    dt: datetime | None = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
    elif isinstance(value, tuple):  # feedparser struct_time
        try:
            dt = datetime(*value[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
    elif isinstance(value, str):
        s = value.strip()
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = parsedate_to_datetime(s)
            except (TypeError, ValueError, IndexError):
                return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if dt.year < 1995 or (dt - now).total_seconds() > 86400 * 2:
        return None  # implausible: far past or more than 2 days in the future
    return dt


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None
