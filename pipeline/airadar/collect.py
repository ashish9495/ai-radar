"""DISCOVER → NORMALIZE → DEDUPLICATE → STORE. Runs every due source; one failing source never stops the rest."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

from .adapters import AdapterUnavailable, Context, registry
from .classify import keyword_filter_pass
from .config import Config
from .dedupe import DedupeIndex
from .http import Http
from .models import RawItem, Source
from .normalize import canonical_url, clean_text, content_hash, iso, normalize_title, sha256
from .store import Store

log = logging.getLogger("airadar.collect")
DEFAULT_MAX_AGE_DAYS = 21  # feeds hand over their whole backlog; skip anything older than this


def too_old(item: RawItem, source: Source, now: datetime) -> bool:
    """True if the item was published longer ago than the source allows (0 disables the check).
    Undated items are kept and shown as 'date unknown'."""
    max_age = int(source.config.get("max_age_days", DEFAULT_MAX_AGE_DAYS))
    return bool(max_age and item.published_at and now - item.published_at > timedelta(days=max_age))


def is_due(source: Source, health: dict | None, now: datetime, grace_minutes: int = 3) -> bool:
    if not health or not health.get("last_attempt_at"):
        return True
    last = datetime.fromisoformat(str(health["last_attempt_at"]).replace("Z", "+00:00"))
    return now - last >= timedelta(minutes=max(source.interval_minutes - grace_minutes, 5))


def health_status(source: Source, health: dict, now: datetime) -> str:
    if not source.enabled:
        return "disabled"
    if health.get("consecutive_failures", 0) >= 3:
        return "failing"
    last_ok = health.get("last_success_at")
    if not last_ok:
        return "failing" if health.get("consecutive_failures") else "unknown"
    last_ok = datetime.fromisoformat(str(last_ok).replace("Z", "+00:00"))
    if now - last_ok > timedelta(minutes=source.interval_minutes * 3 + 30):
        return "delayed"
    return "healthy"


def to_row(item: RawItem, source: Source) -> dict:
    url = canonical_url(item.url)
    ntitle = normalize_title(item.title)
    dtype = item.discovery_type or ("news" if source.adapter in ("rss", "web_search") else "other")
    return {
        "title": item.title[:400],
        "normalized_title": ntitle,
        "canonical_url": url,
        "url_hash": sha256(url),
        "content_hash": content_hash(item.excerpt),
        "discovery_type": dtype,
        "primary_category": source.default_category,
        "published_at": iso(item.published_at),
        "released_at": iso(item.released_at),
        "updated_at_source": iso(item.updated_at_source),
        "raw_excerpt": clean_text(item.excerpt, 3000) or None,
        "stars": item.stars,
        "license": item.license,
        "is_open_source": item.is_open_source,
        "is_hidden_gem": bool(item.extra.get("hidden_gem_candidate")),
        "maintenance_signals": item.extra.get("maintenance"),
        "extra": {k: v for k, v in item.extra.items() if k not in ("maintenance",)}
                 | {"author": item.author, "points": item.score, "comments": item.comments},
    }


def collect_source(source: Source, ctx: Context, store: Store, index: DedupeIndex, categories, workflow_run_id) -> dict:
    run_id = store.start_ingestion(source.id, workflow_run_id)
    stats = {"items_fetched": 0, "items_new": 0, "items_duplicate": 0, "items_too_old": 0}
    now = datetime.now(timezone.utc)
    try:
        items = registry()[source.adapter](source, ctx)
    except AdapterUnavailable as exc:
        store.finish_ingestion(run_id, {**stats, "status": "skipped", "error": str(exc)[:500]})
        return {"status": "skipped", "error": str(exc), **stats}
    except Exception as exc:  # noqa: BLE001 — isolate every source
        msg = f"{type(exc).__name__}: {exc}"[:500]
        log.error("source %s failed: %s", source.id, msg)
        store.finish_ingestion(run_id, {**stats, "status": "failed", "error": msg})
        return {"status": "failed", "error": msg, **stats}

    stats["items_fetched"] = len(items)
    newest_pub = None
    errors = 0
    for item in items:
        try:
            if source.config.get("keyword_filter") and not keyword_filter_pass(item, categories):
                continue
            if too_old(item, source, now):
                stats["items_too_old"] += 1
                continue
            row = to_row(item, source)
            if item.published_at and (newest_pub is None or item.published_at > newest_pub):
                newest_pub = item.published_at
            match = index.match(row["url_hash"], row["content_hash"], row["normalized_title"], row["canonical_url"])
            raw_meta = {"external_title": item.title, "points": item.score, "comments": item.comments,
                        "discussion_url": item.extra.get("discussion_url")}
            if match:
                stats["items_duplicate"] += 1
                store.add_sighting(match.discovery_id, source.id, item.url, item.external_id,
                                   raw_meta | {"dedupe_reason": match.reason, "similarity": match.similarity})
                continue
            did = store.insert_discovery(row | {"dedupe_meta": {"first_source": source.id}})
            index.add(did, row["url_hash"], row["content_hash"], row["normalized_title"], row["canonical_url"])
            store.add_sighting(did, source.id, item.url, item.external_id, raw_meta)
            stats["items_new"] += 1
        except Exception as exc:  # noqa: BLE001 — a bad item must not abort the source
            errors += 1
            log.warning("item failed in %s: %s", source.id, type(exc).__name__)
    status = "partial" if errors else "success"
    store.finish_ingestion(run_id, {**stats, "status": status, "error": f"{errors} item errors" if errors else None})
    return {"status": status, "newest_published": newest_pub, **stats}


def run(store: Store, config: Config, http: Http, only: list[str] | None = None, force: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    wf = store.start_workflow("collect", config.github_run_id, config.github_run_url)
    sources = [s for s in store.list_sources() if s.enabled and (not only or s.id in only)]
    categories = store.list_categories()
    health = store.all_health()
    index = DedupeIndex(store.recent_index(days=7))
    summary: dict[str, dict] = {}
    for source in sources:
        h = health.get(source.id, {})
        if not force and not is_due(source, h, now):
            summary[source.id] = {"status": "not_due"}
            continue
        since = h.get("last_success_at")
        ctx = Context(http=http, config=config,
                      since=datetime.fromisoformat(str(since).replace("Z", "+00:00")) if since else None)
        log.info("collecting %s (%s)", source.id, source.adapter)
        result = collect_source(source, ctx, store, index, categories, wf)
        summary[source.id] = {k: v for k, v in result.items() if k != "newest_published"}
        attempt = datetime.now(timezone.utc)
        upd: dict = {"last_attempt_at": iso(attempt)}
        if result["status"] in ("success", "partial"):
            upd.update(last_success_at=iso(attempt), consecutive_failures=0, last_error=None)
            if result.get("newest_published"):
                upd["last_item_published_at"] = iso(result["newest_published"])
        elif result["status"] == "failed":
            upd.update(consecutive_failures=h.get("consecutive_failures", 0) + 1, last_error=result.get("error"))
        else:  # skipped
            upd.update(last_error=result.get("error"))
        merged = {**h, **upd}
        upd["status"] = health_status(source, merged, attempt)
        store.upsert_health(source.id, upd)
        health[source.id] = {**merged, "status": upd["status"]}

    ran = [v for v in summary.values() if v["status"] != "not_due"]
    failed = sum(1 for v in ran if v["status"] == "failed")
    status = "failed" if ran and failed == len(ran) else "partial" if failed else "success"
    totals = {k: sum(v.get(k, 0) for v in ran) for k in ("items_fetched", "items_new", "items_duplicate", "items_too_old")}
    store.finish_workflow(wf, {"status": status, "stats": {"sources": summary, **totals, "config": config.status()},
                               "error": f"{failed} source(s) failed" if failed else None})
    return {"status": status, "sources": summary, **totals}


def main(argv: list[str] | None = None) -> int:
    from .cli import build_store, setup_logging
    p = argparse.ArgumentParser(description="Collect discoveries from due sources")
    p.add_argument("--source", action="append", help="limit to source id (repeatable)")
    p.add_argument("--force", action="store_true", help="ignore per-source intervals")
    p.add_argument("--dry-run", action="store_true", help="use an in-memory store seeded from supabase/seed.sql")
    args = p.parse_args(argv)
    setup_logging()
    config = Config()
    store = build_store(config, dry_run=args.dry_run)
    http = Http(config.user_agent)
    try:
        result = run(store, config, http, only=args.source, force=args.force or args.dry_run)
    finally:
        http.close()
    for sid, r in result["sources"].items():
        log.info("%-20s %-8s fetched=%s new=%s dup=%s too_old=%s %s", sid, r["status"], r.get("items_fetched", "-"),
                 r.get("items_new", "-"), r.get("items_duplicate", "-"), r.get("items_too_old", "-"), r.get("error") or "")
    log.info("collect finished: %s (new=%d, duplicates=%d)", result["status"], result["items_new"], result["items_duplicate"])
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
