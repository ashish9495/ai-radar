"""VERIFY → CATEGORIZE → RANK → SUMMARIZE for pending discoveries."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

from .classify import categorize, extract_tags, guess_pricing, infer_type
from .config import Config
from .http import Http
from .llm import BudgetExceeded, Summarizer, build_provider
from .normalize import iso
from .rank import score_item
from .store import Store
from .verify import verification_status

log = logging.getLogger("airadar.process")


def _dt(v):
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")) if v else None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def heuristic_summary(item: dict) -> str | None:
    text = (item.get("raw_excerpt") or "").strip()
    if not text:
        return None
    cut = text[:280]
    if len(text) > 280:
        cut = cut.rsplit(" ", 1)[0] + "…"
    return cut


def process_item(item: dict, *, sources_by_id, categories, summarizer: Summarizer, min_score_for_llm: float,
                 now: datetime) -> dict:
    sightings = item.get("discovery_sources") or []
    srcs = [sources_by_id[s["source_id"]] for s in sightings if s["source_id"] in sources_by_id]
    default_cat = next((s.default_category for s in srcs if s.default_category), None)
    title, body = item["title"], item.get("raw_excerpt")
    extra = item.get("extra") or {}

    dtype = infer_type(item.get("discovery_type") or "news", title, body)
    cats = categorize(title, body, categories, default=default_cat)
    tags = extract_tags(title, body, extra_tags=(extra.get("topics") or [])[:3])
    pricing = guess_pricing(title, body, item.get("license"))
    status, evidence = verification_status(item["canonical_url"], srcs, dtype)
    points = max([s.get("raw_meta", {}).get("points") or 0 for s in sightings] + [0]) or None
    comments = max([s.get("raw_meta", {}).get("comments") or 0 for s in sightings] + [0]) or None
    cat_map = {c.slug: c for c in categories}

    args = dict(published=_dt(item.get("published_at")), discovered=_dt(item["first_discovered_at"]),
                verification=status, sources=srcs, cat_slugs=cats, categories=cat_map, pricing=pricing,
                points=points, comments=comments, dtype=dtype, now=now)
    score, breakdown, label = score_item(usefulness=None, **args)

    update: dict = {
        "discovery_type": dtype, "primary_category": cats[0] if cats else default_cat,
        "verification_status": status, "pricing": pricing,
        "summary_short": item.get("summary_short") or heuristic_summary(item),
        "last_verified_at": iso(now) if evidence else item.get("last_verified_at"),
    }
    llm_note = "heuristic"
    if summarizer.available and score >= min_score_for_llm:
        try:
            out = summarizer.summarize(item, [s.name for s in srcs], set(cat_map), strong=score >= 65)
            update.update({k: out[k] for k in ("summary_short", "summary_detailed", "why_it_matters",
                                               "practical_usefulness", "known_limitations", "claims_note") if out.get(k)})
            if out["discovery_type"] and dtype in ("news", "other"):
                update["discovery_type"] = dtype = out["discovery_type"]
            if pricing == "unknown" and out["pricing"] != "unknown":
                update["pricing"] = pricing = out["pricing"]
            if out["categories"]:
                cats = list(dict.fromkeys(out["categories"] + cats))[:3]
                update["primary_category"] = cats[0]
            tags = list(dict.fromkeys(tags + out["tags"]))[:8]
            if out["is_hidden_gem"] and (item.get("stars") or 0) < 5000:
                update["is_hidden_gem"] = True
            update["model_used"] = out["model_used"]
            args.update(cat_slugs=cats, pricing=pricing, dtype=dtype)
            score, breakdown, label = score_item(usefulness=out["usefulness_score"], **args)
            llm_note = "llm"
        except BudgetExceeded as exc:
            llm_note = f"budget: {exc}"
        except Exception as exc:  # noqa: BLE001 — keep heuristic result on model failure
            llm_note = f"llm_error: {type(exc).__name__}"
            log.warning("summarize failed for %s: %s", item["id"], exc)

    breakdown["method"] = llm_note
    update.update({"score": score, "score_breakdown": breakdown, "importance": label,
                   "processing_status": "processed", "processed_at": iso(now), "processing_error": None})
    return {"update": update, "categories": cats, "tags": tags, "evidence": evidence}


def run(store: Store, config: Config, http: Http, limit: int | None = None) -> dict:
    now = datetime.now(timezone.utc)
    wf = store.start_workflow("process", config.github_run_id, config.github_run_url)
    settings = store.get_settings()
    budget = min(_num(settings.get("daily_budget_usd")) or config.daily_budget_usd_cap, config.daily_budget_usd_cap)
    min_score = _num(settings.get("summarize_min_score")) or 35
    limit = limit or int(_num(settings.get("max_items_per_process_run")) or 60)
    summarizer = Summarizer(build_provider(config, http), config, store, budget)
    sources_by_id = {s.id: s for s in store.list_sources()}
    categories = store.list_categories()
    stats = {"processed": 0, "failed": 0, "llm": 0, "heuristic": 0, "budget_stopped": 0}
    for item in store.pending_discoveries(limit):
        try:
            res = process_item(item, sources_by_id=sources_by_id, categories=categories, summarizer=summarizer,
                               min_score_for_llm=min_score, now=now)
            store.update_discovery(item["id"], res["update"])
            store.set_categories(item["id"], res["categories"])
            store.set_tags(item["id"], res["tags"])
            for url, kind in res["evidence"]:
                store.add_evidence(item["id"], url, kind)
            method = res["update"]["score_breakdown"]["method"]
            stats["processed"] += 1
            stats["llm" if method == "llm" else "budget_stopped" if method.startswith("budget") else "heuristic"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            log.error("processing failed for %s: %s", item.get("id"), type(exc).__name__)
            store.update_discovery(item["id"], {"processing_status": "failed",
                                                "processing_error": f"{type(exc).__name__}: {exc}"[:500]})
    status = "failed" if stats["failed"] and not stats["processed"] else "partial" if stats["failed"] else "success"
    store.finish_workflow(wf, {"status": status, "stats": stats | {"config": config.status(), "llm_enabled": summarizer.available,
                                                                   "spent_today_usd": round(summarizer.spent_today, 4)}})
    return {"status": status, **stats}


def main(argv: list[str] | None = None) -> int:
    from .cli import build_store, setup_logging
    p = argparse.ArgumentParser(description="Verify, categorise, rank and summarise pending discoveries")
    p.add_argument("--limit", type=int)
    args = p.parse_args(argv)
    setup_logging()
    config = Config()
    store = build_store(config)
    http = Http(config.user_agent)
    try:
        result = run(store, config, http, limit=args.limit)
    finally:
        http.close()
    log.info("process finished: %s", result)
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
