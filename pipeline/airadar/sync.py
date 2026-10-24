"""Sync config/sources.json and config/categories.json into Supabase.

New sources are inserted with their configured defaults. For existing sources, adapter settings are
updated but the dashboard-editable fields (enabled, interval_minutes, notes / category enabled, priority)
are preserved so changes made in Settings are not overwritten."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from .config import Config

log = logging.getLogger("airadar.sync")
ROOT = Path(__file__).resolve().parents[2]
SOURCE_LOCKED = {"enabled", "interval_minutes", "notes"}
CATEGORY_LOCKED = {"enabled", "priority"}
ADAPTERS = {"rss", "github_releases", "github_search", "hackernews", "reddit", "huggingface", "arxiv", "web_search"}


def load_config(root: Path = ROOT) -> tuple[list[dict], list[dict]]:
    sources = json.loads((root / "config" / "sources.json").read_text(encoding="utf-8"))
    categories = json.loads((root / "config" / "categories.json").read_text(encoding="utf-8"))
    validate(sources, categories)
    return sources, categories


def validate(sources: list[dict], categories: list[dict]) -> None:
    slugs = {c["slug"] for c in categories}
    ids = set()
    for s in sources:
        if s["id"] in ids:
            raise ValueError(f"duplicate source id {s['id']}")
        ids.add(s["id"])
        if s["adapter"] not in ADAPTERS:
            raise ValueError(f"{s['id']}: unknown adapter {s['adapter']}")
        if s.get("default_category") and s["default_category"] not in slugs:
            raise ValueError(f"{s['id']}: unknown category {s['default_category']}")
        if s.get("interval_minutes", 60) < 15:
            raise ValueError(f"{s['id']}: interval below 15 minutes")
        blob = json.dumps(s["config"]).lower()
        if any(word in blob for word in ("api_key", "apikey", "token", "secret", "password")):
            raise ValueError(f"{s['id']}: config must not contain credentials")


def main() -> int:
    from .cli import setup_logging
    from .store import SupabaseStore
    setup_logging()
    cfg = Config()
    sources, categories = load_config()
    if not (cfg.supabase_url and cfg.supabase_service_key):
        log.info("config valid (%d sources, %d categories); Supabase not configured, nothing synced", len(sources), len(categories))
        return 0
    st = SupabaseStore(cfg.supabase_url, cfg.supabase_service_key)
    existing_cats = {r["slug"] for r in st._get("/categories", select="slug")}
    for c in categories:
        if c["slug"] in existing_cats:
            st._patch("/categories", {k: v for k, v in c.items() if k not in CATEGORY_LOCKED | {"slug"}}, slug=f"eq.{c['slug']}")
        else:
            st._post("/categories", c, prefer="return=minimal")
    existing = {r["id"] for r in st._get("/sources", select="id")}
    for s in sources:
        if s["id"] in existing:
            st._patch("/sources", {k: v for k, v in s.items() if k not in SOURCE_LOCKED | {"id"}}, id=f"eq.{s['id']}")
        else:
            st._post("/sources", s, prefer="return=minimal")
            st.upsert_health(s["id"], {"status": "unknown" if s.get("enabled", True) else "disabled"})
    removed = existing - {s["id"] for s in sources}
    if removed:
        log.warning("sources in DB but not in config (left untouched, disable them in Settings): %s", sorted(removed))
    log.info("synced %d categories and %d sources", len(categories), len(sources))
    return 0


if __name__ == "__main__":
    sys.exit(main())
