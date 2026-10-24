"""GitHub REST API: watched-repo releases and searches for rising repositories."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ..http import FetchError
from ..models import RawItem, Source
from ..normalize import clean_text, parse_datetime
from . import Context

log = logging.getLogger(__name__)
API = "https://api.github.com"


def _headers(ctx: Context) -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if ctx.config.github_token:
        h["Authorization"] = f"Bearer {ctx.config.github_token}"
    return h


def _repo_meta(ctx: Context, full_name: str) -> dict:
    try:
        return ctx.http.get(f"{API}/repos/{full_name}", headers=_headers(ctx)).json()
    except FetchError as exc:
        log.warning("repo metadata failed for %s: %s", full_name, exc)
        return {}


def _maintenance(meta: dict) -> dict:
    return {k: meta.get(k) for k in ("pushed_at", "open_issues_count", "archived", "forks_count", "default_branch")
            if k in meta}


def fetch_releases(source: Source, ctx: Context) -> list[RawItem]:
    items: list[RawItem] = []
    errors: list[str] = []
    per_repo = int(source.config.get("per_repo", 2))
    for full_name in source.config.get("repos", []):
        try:
            releases = ctx.http.get(f"{API}/repos/{full_name}/releases",
                                    params={"per_page": per_repo}, headers=_headers(ctx)).json()
        except FetchError as exc:
            errors.append(f"{full_name}: {exc}")
            continue
        meta = _repo_meta(ctx, full_name) if releases else {}
        for rel in releases:
            if rel.get("draft"):
                continue
            name = rel.get("name") or rel.get("tag_name") or "release"
            title = f"{full_name} {name}" if full_name.split("/")[1].lower() not in name.lower() else name
            published = parse_datetime(rel.get("published_at"))
            items.append(RawItem(
                source_id=source.id,
                title=clean_text(title, 300),
                url=rel["html_url"],
                excerpt=clean_text(rel.get("body"), 3000),
                published_at=published,
                released_at=published,
                external_id=str(rel.get("id")),
                discovery_type="repo",
                stars=meta.get("stargazers_count"),
                license=(meta.get("license") or {}).get("spdx_id"),
                is_open_source=bool(meta.get("license")) if meta else None,
                extra={"repo": full_name, "prerelease": rel.get("prerelease", False),
                       "repo_url": f"https://github.com/{full_name}", "maintenance": _maintenance(meta),
                       "topics": meta.get("topics", [])},
            ))
    if errors and not items:
        raise FetchError("; ".join(errors[:3]))
    if errors:
        log.warning("github_releases partial failures: %s", "; ".join(errors[:5]))
    return items


def fetch_search(source: Source, ctx: Context) -> list[RawItem]:
    days = int(source.config.get("created_within_days", 30))
    min_stars = int(source.config.get("min_stars", 50))
    per_query = int(source.config.get("per_query", 10))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    seen: set[str] = set()
    items: list[RawItem] = []
    for q in source.config.get("queries", []):
        query = f"{q} created:>{since} stars:>={min_stars} archived:false"
        data = ctx.http.get(f"{API}/search/repositories",
                            params={"q": query, "sort": "stars", "order": "desc", "per_page": per_query},
                            headers=_headers(ctx)).json()
        for repo in data.get("items", []):
            if repo["full_name"] in seen:
                continue
            seen.add(repo["full_name"])
            lic = (repo.get("license") or {}).get("spdx_id")
            items.append(RawItem(
                source_id=source.id,
                title=f"{repo['full_name']}: {clean_text(repo.get('description') or 'repository', 200)}",
                url=repo["html_url"],
                excerpt=clean_text(repo.get("description"), 1000),
                published_at=parse_datetime(repo.get("created_at")),
                updated_at_source=parse_datetime(repo.get("pushed_at")),
                external_id=str(repo["id"]),
                discovery_type="repo",
                stars=repo.get("stargazers_count"),
                license=lic if lic and lic != "NOASSERTION" else None,
                is_open_source=bool(lic and lic != "NOASSERTION"),
                extra={"repo": repo["full_name"], "language": repo.get("language"), "topics": repo.get("topics", []),
                       "maintenance": _maintenance(repo), "hidden_gem_candidate": repo.get("stargazers_count", 0) < 2000},
            ))
    return items
