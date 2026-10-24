"""Persistence layer. SupabaseStore talks to PostgREST with the service-role key (pipeline only).
MemoryStore implements the same interface for tests and dry runs."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .models import Category, Source
from .normalize import iso


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Store:
    """Interface. All datetimes passed in are aware UTC."""

    def list_sources(self) -> list[Source]: ...
    def list_categories(self) -> list[Category]: ...
    def get_settings(self) -> dict[str, Any]: ...
    def all_health(self) -> dict[str, dict]: ...
    def upsert_health(self, source_id: str, fields: dict) -> None: ...
    def recent_index(self, days: int) -> list[dict]: ...
    def insert_discovery(self, row: dict) -> str: ...
    def update_discovery(self, discovery_id: str, fields: dict) -> None: ...
    def add_sighting(self, discovery_id: str, source_id: str, url: str, external_id: str | None, raw_meta: dict) -> None: ...
    def start_ingestion(self, source_id: str, workflow_run_id: str | None) -> str: ...
    def finish_ingestion(self, run_id: str, fields: dict) -> None: ...
    def start_workflow(self, workflow: str, github_run_id: str | None, github_run_url: str | None) -> str: ...
    def finish_workflow(self, run_id: str, fields: dict) -> None: ...
    def pending_discoveries(self, limit: int) -> list[dict]: ...
    def set_categories(self, discovery_id: str, slugs: list[str]) -> None: ...
    def set_tags(self, discovery_id: str, names: list[str]) -> None: ...
    def log_usage(self, row: dict) -> None: ...
    def cost_today(self) -> float: ...
    def top_since(self, since: datetime, limit: int) -> list[dict]: ...
    def upsert_briefing(self, row: dict) -> None: ...
    def add_evidence(self, discovery_id: str, url: str, kind: str) -> None: ...


class SupabaseStore(Store):
    def __init__(self, url: str, service_key: str, transport: httpx.BaseTransport | None = None):
        headers = {"apikey": service_key, "Content-Type": "application/json"}
        if not service_key.startswith("sb_"):  # legacy JWT service_role key
            headers["Authorization"] = f"Bearer {service_key}"
        self.c = httpx.Client(base_url=f"{url.rstrip('/')}/rest/v1", headers=headers, timeout=30, transport=transport)

    # -- helpers --------------------------------------------------------
    def _get(self, path: str, **params) -> list[dict]:
        r = self.c.get(path, params=params)
        self._check(r)
        return r.json()

    def _post(self, path: str, body, prefer: str = "return=representation", **params) -> list[dict]:
        r = self.c.post(path, json=body, params=params, headers={"Prefer": prefer})
        self._check(r)
        return r.json() if r.content else []

    def _patch(self, path: str, body: dict, **params) -> None:
        self._check(self.c.patch(path, json=body, params=params, headers={"Prefer": "return=minimal"}))

    def _delete(self, path: str, **params) -> None:
        self._check(self.c.delete(path, params=params))

    @staticmethod
    def _check(r: httpx.Response) -> None:
        if r.status_code >= 400:
            # PostgREST error bodies contain no secrets; truncate anyway.
            raise RuntimeError(f"Supabase {r.request.method} {r.request.url.path} -> {r.status_code}: {r.text[:300]}")

    # -- reference data -------------------------------------------------
    def list_sources(self) -> list[Source]:
        return [Source.from_row(r) for r in self._get("/sources", select="*", order="id")]

    def list_categories(self) -> list[Category]:
        return [Category.from_row(r) for r in self._get("/categories", select="*", order="priority")]

    def get_settings(self) -> dict[str, Any]:
        return {r["key"]: r["value"] for r in self._get("/app_settings", select="key,value")}

    def all_health(self) -> dict[str, dict]:
        return {r["source_id"]: r for r in self._get("/source_health", select="*")}

    def upsert_health(self, source_id: str, fields: dict) -> None:
        self._post("/source_health", {"source_id": source_id, **fields, "updated_at": iso(_now())},
                   prefer="resolution=merge-duplicates,return=minimal", on_conflict="source_id")

    # -- discoveries ----------------------------------------------------
    def recent_index(self, days: int) -> list[dict]:
        # Supabase caps responses (default 1000 rows), so page through explicitly.
        since = iso(_now() - timedelta(days=days))
        rows: list[dict] = []
        while len(rows) < 10000:
            page = self._get("/discoveries", select="id,title,normalized_title,canonical_url,url_hash,content_hash,first_discovered_at",
                             first_discovered_at=f"gte.{since}", order="first_discovered_at.desc,id",
                             limit="1000", offset=str(len(rows)))
            rows += page
            if len(page) < 1000:
                break
        return rows

    def find_by_url_hash(self, url_hash: str) -> dict | None:
        rows = self._get("/discoveries", select="id,title,normalized_title,canonical_url,url_hash,content_hash,first_discovered_at",
                         url_hash=f"eq.{url_hash}")
        return rows[0] if rows else None

    def insert_discovery(self, row: dict) -> str:
        # on_conflict makes concurrent/re-run inserts idempotent.
        res = self._post("/discoveries", row, prefer="resolution=ignore-duplicates,return=representation",
                         on_conflict="url_hash", select="id")
        if res:
            return res[0]["id"]
        existing = self.find_by_url_hash(row["url_hash"])
        assert existing, "insert ignored but row not found"
        return existing["id"]

    def update_discovery(self, discovery_id: str, fields: dict) -> None:
        self._patch("/discoveries", fields, id=f"eq.{discovery_id}")

    def add_sighting(self, discovery_id, source_id, url, external_id, raw_meta) -> None:
        self._post("/discovery_sources", {"discovery_id": discovery_id, "source_id": source_id, "source_url": url,
                                          "external_id": external_id, "raw_meta": raw_meta, "seen_at": iso(_now())},
                   prefer="resolution=merge-duplicates,return=minimal", on_conflict="discovery_id,source_id,source_url")

    def pending_discoveries(self, limit: int) -> list[dict]:
        return self._get("/discoveries", select="*,discovery_sources(source_id,source_url,raw_meta)",
                         processing_status="eq.pending", duplicate_of="is.null",
                         order="first_discovered_at.desc", limit=str(limit))

    def set_categories(self, discovery_id: str, slugs: list[str]) -> None:
        self._delete("/discovery_categories", discovery_id=f"eq.{discovery_id}")
        if slugs:
            self._post("/discovery_categories", [{"discovery_id": discovery_id, "category_slug": s} for s in slugs],
                       prefer="resolution=ignore-duplicates,return=minimal")

    def set_tags(self, discovery_id: str, names: list[str]) -> None:
        self._delete("/discovery_tags", discovery_id=f"eq.{discovery_id}")
        rows = [{"slug": _slug(n), "name": n[:60]} for n in dict.fromkeys(names) if _slug(n)]
        if not rows:
            return
        self._post("/tags", rows, prefer="resolution=ignore-duplicates,return=minimal", on_conflict="slug")
        slugs = ",".join(f'"{r["slug"]}"' for r in rows)
        tags = self._get("/tags", select="id,slug", slug=f"in.({slugs})")
        self._post("/discovery_tags", [{"discovery_id": discovery_id, "tag_id": t["id"]} for t in tags],
                   prefer="resolution=ignore-duplicates,return=minimal")

    def add_evidence(self, discovery_id: str, url: str, kind: str) -> None:
        self._post("/evidence_links", {"discovery_id": discovery_id, "url": url, "kind": kind},
                   prefer="resolution=ignore-duplicates,return=minimal", on_conflict="discovery_id,url")

    # -- runs -----------------------------------------------------------
    def start_ingestion(self, source_id, workflow_run_id) -> str:
        return self._post("/ingestion_runs", {"source_id": source_id, "workflow_run_id": workflow_run_id}, select="id")[0]["id"]

    def finish_ingestion(self, run_id, fields) -> None:
        self._patch("/ingestion_runs", {**fields, "finished_at": iso(_now())}, id=f"eq.{run_id}")

    def start_workflow(self, workflow, github_run_id, github_run_url) -> str:
        return self._post("/workflow_runs", {"workflow": workflow, "github_run_id": github_run_id,
                                             "github_run_url": github_run_url}, select="id")[0]["id"]

    def finish_workflow(self, run_id, fields) -> None:
        self._patch("/workflow_runs", {**fields, "finished_at": iso(_now())}, id=f"eq.{run_id}")

    # -- usage ----------------------------------------------------------
    def log_usage(self, row: dict) -> None:
        self._post("/api_usage", row, prefer="return=minimal")

    def cost_today(self) -> float:
        start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
        rows = self._get("/api_usage", select="est_cost_usd", created_at=f"gte.{iso(start)}")
        return float(sum(float(r["est_cost_usd"]) for r in rows))

    # -- briefing -------------------------------------------------------
    def top_since(self, since: datetime, limit: int) -> list[dict]:
        return self._get("/discoveries", select="id,title,canonical_url,summary_short,why_it_matters,importance,score,discovery_type,primary_category,verification_status",
                         first_discovered_at=f"gte.{iso(since)}", duplicate_of="is.null", processing_status="eq.processed",
                         order="score.desc", limit=str(limit))

    def upsert_briefing(self, row: dict) -> None:
        self._post("/briefings", row, prefer="resolution=merge-duplicates,return=minimal", on_conflict="briefing_date")


class MemoryStore(Store):
    """In-memory implementation used by tests and `--dry-run`."""

    def __init__(self, sources: list[Source] | None = None, categories: list[Category] | None = None,
                 settings: dict | None = None):
        self.sources = sources or []
        self.categories = categories or []
        self.settings = settings or {}
        self.discoveries: dict[str, dict] = {}
        self.sightings: list[dict] = []
        self.health: dict[str, dict] = {}
        self.ingestion: dict[str, dict] = {}
        self.workflows: dict[str, dict] = {}
        self.cats: dict[str, list[str]] = {}
        self.tags: dict[str, list[str]] = {}
        self.usage: list[dict] = []
        self.briefings: dict[str, dict] = {}
        self.evidence: set[tuple[str, str, str]] = set()

    def list_sources(self): return list(self.sources)
    def list_categories(self): return list(self.categories)
    def get_settings(self): return dict(self.settings)
    def all_health(self): return {k: dict(v) for k, v in self.health.items()}

    def upsert_health(self, source_id, fields):
        self.health.setdefault(source_id, {"source_id": source_id, "consecutive_failures": 0}).update(fields)

    def recent_index(self, days):
        since = _now() - timedelta(days=days)
        return [d for d in self.discoveries.values() if _as_dt(d["first_discovered_at"]) >= since]

    def find_by_url_hash(self, url_hash):
        return next((d for d in self.discoveries.values() if d["url_hash"] == url_hash), None)

    def insert_discovery(self, row):
        existing = self.find_by_url_hash(row["url_hash"])
        if existing:
            return existing["id"]
        did = str(uuid.uuid4())
        self.discoveries[did] = {"id": did, "processing_status": "pending", "duplicate_of": None,
                                 "first_discovered_at": iso(_now()), **row}
        return did

    def update_discovery(self, discovery_id, fields):
        self.discoveries[discovery_id].update(fields)

    def add_sighting(self, discovery_id, source_id, url, external_id, raw_meta):
        key = (discovery_id, source_id, url)
        if not any((s["discovery_id"], s["source_id"], s["source_url"]) == key for s in self.sightings):
            self.sightings.append({"discovery_id": discovery_id, "source_id": source_id, "source_url": url,
                                   "external_id": external_id, "raw_meta": raw_meta})

    def pending_discoveries(self, limit):
        rows = [dict(d, discovery_sources=[s for s in self.sightings if s["discovery_id"] == d["id"]])
                for d in self.discoveries.values()
                if d.get("processing_status") == "pending" and not d.get("duplicate_of")]
        return rows[:limit]

    def set_categories(self, discovery_id, slugs): self.cats[discovery_id] = list(slugs)
    def set_tags(self, discovery_id, names): self.tags[discovery_id] = list(dict.fromkeys(names))
    def add_evidence(self, discovery_id, url, kind): self.evidence.add((discovery_id, url, kind))

    def start_ingestion(self, source_id, workflow_run_id):
        rid = str(uuid.uuid4()); self.ingestion[rid] = {"source_id": source_id, "status": "running"}; return rid

    def finish_ingestion(self, run_id, fields): self.ingestion[run_id].update(fields)

    def start_workflow(self, workflow, github_run_id, github_run_url):
        rid = str(uuid.uuid4()); self.workflows[rid] = {"workflow": workflow, "status": "running"}; return rid

    def finish_workflow(self, run_id, fields): self.workflows[run_id].update(fields)
    def log_usage(self, row): self.usage.append(row)
    def cost_today(self): return float(sum(u.get("est_cost_usd", 0) for u in self.usage))

    def top_since(self, since, limit):
        rows = [d for d in self.discoveries.values()
                if d.get("processing_status") == "processed" and not d.get("duplicate_of")
                and _as_dt(d["first_discovered_at"]) >= since]
        return sorted(rows, key=lambda d: d.get("score", 0), reverse=True)[:limit]

    def upsert_briefing(self, row): self.briefings[row["briefing_date"]] = row


def _as_dt(v) -> datetime:
    return v if isinstance(v, datetime) else datetime.fromisoformat(str(v).replace("Z", "+00:00"))
