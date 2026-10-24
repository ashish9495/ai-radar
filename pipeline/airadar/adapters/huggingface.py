"""Hugging Face Hub public API (models / spaces / datasets)."""
from __future__ import annotations

from ..models import RawItem, Source
from ..normalize import parse_datetime
from . import Context

TYPE_MAP = {"models": "model", "spaces": "tool", "datasets": "dataset"}


def fetch(source: Source, ctx: Context) -> list[RawItem]:
    kind = source.config.get("kind", "models")
    params = {"sort": source.config.get("sort", "trendingScore"), "limit": int(source.config.get("limit", 25)),
              "full": "false"}
    data = ctx.http.get(f"https://huggingface.co/api/{kind}", params=params).json()
    items = []
    prefix = "" if kind == "models" else f"{kind}/"
    for m in data:
        rid = m.get("id") or m.get("modelId")
        if not rid:
            continue
        tags = m.get("tags", []) or []
        lic = next((t.split(":", 1)[1] for t in tags if t.startswith("license:")), None)
        pipeline_tag = m.get("pipeline_tag")
        desc = f"Hugging Face {TYPE_MAP.get(kind, 'item')}" + (f" for {pipeline_tag}" if pipeline_tag else "")
        items.append(RawItem(
            source_id=source.id,
            title=f"{rid}" + (f" ({pipeline_tag})" if pipeline_tag else ""),
            url=f"https://huggingface.co/{prefix}{rid}",
            excerpt=f"{desc}. Tags: {', '.join(t for t in tags if ':' not in t)[:400]}",
            published_at=parse_datetime(m.get("createdAt")),
            updated_at_source=parse_datetime(m.get("lastModified")),
            external_id=rid,
            discovery_type=TYPE_MAP.get(kind, "other"),
            score=m.get("likes"),
            license=lic,
            is_open_source=None,  # open weights != open source; leave unknown unless license is OSI
            extra={"downloads": m.get("downloads"), "likes": m.get("likes"), "pipeline_tag": pipeline_tag,
                   "library": m.get("library_name"), "hidden_gem_candidate": (m.get("likes") or 0) < 300},
        ))
    return items
