"""Explainable ranking. Every score comes with a per-factor breakdown stored alongside it."""
from __future__ import annotations

import math
from datetime import datetime, timezone

from .models import Category, Source

WEIGHTS = {"recency": 25, "evidence": 20, "usefulness": 20, "relevance": 20, "novelty": 10, "cost": 5}


def recency_factor(published: datetime | None, discovered: datetime, now: datetime) -> float:
    ref = published or discovered
    hours = max(0.0, (now - ref).total_seconds() / 3600)
    factor = math.exp(-hours / 48)  # half-life ≈ 33h
    return factor * (0.85 if published is None else 1.0)  # unknown publish date: slight penalty


def evidence_factor(verification: str, best_reliability: int) -> float:
    base = {"official": 1.0, "multi_source": 0.85, "source_reported": 0.55, "unverified": 0.3, "disputed": 0.1}[verification]
    return min(1.0, base * (0.6 + 0.08 * best_reliability))


def relevance_factor(cat_slugs: list[str], categories: dict[str, Category]) -> float:
    if not cat_slugs:
        return 0.2
    best = min((categories[c].priority for c in cat_slugs if c in categories), default=9)
    return max(0.2, 1.0 - (best - 1) * 0.09)


def community_factor(points: int | None, comments: int | None) -> float:
    if not points and not comments:
        return 0.0
    return min(1.0, math.log10(1 + (points or 0) + 2 * (comments or 0)) / 3)


def score_item(*, published: datetime | None, discovered: datetime, verification: str, sources: list[Source],
               cat_slugs: list[str], categories: dict[str, Category], pricing: str, usefulness: float | None,
               points: int | None = None, comments: int | None = None, dtype: str = "news",
               now: datetime | None = None) -> tuple[float, dict, str]:
    now = now or datetime.now(timezone.utc)
    best_rel = max((s.reliability for s in sources), default=2)
    f = {
        "recency": recency_factor(published, discovered, now),
        "evidence": evidence_factor(verification, best_rel),
        # LLM usefulness (0–10) when available, otherwise community signal + type prior
        "usefulness": (usefulness / 10) if usefulness is not None else
                      max(community_factor(points, comments), 0.5 if dtype in ("tool", "repo", "workflow", "agent") else 0.35),
        "relevance": relevance_factor(cat_slugs, categories),
        "novelty": min(1.0, 0.4 + 0.3 * len(sources)) if dtype in ("model", "tool", "agent", "repo") else 0.5,
        "cost": {"free": 1.0, "open_source": 1.0, "freemium": 0.8, "unknown": 0.5, "paid": 0.4, "enterprise": 0.2}.get(pricing, 0.5),
    }
    breakdown = {k: round(v * WEIGHTS[k], 2) for k, v in f.items()}
    total = round(sum(breakdown.values()), 2)
    return total, breakdown, label_for(total, f, dtype, verification)


def label_for(total: float, f: dict, dtype: str, verification: str) -> str:
    if total >= 70 and f["evidence"] >= 0.5:
        return "must_know"
    if dtype in ("paper",) and total >= 50:
        return "watchlist"
    if total >= 55 and dtype in ("tool", "repo", "agent", "workflow", "model"):
        return "worth_trying" if verification in ("official", "multi_source", "source_reported") else "experimental"
    if total >= 50:
        return "worth_trying" if f["evidence"] >= 0.5 else "experimental"
    if total >= 35:
        return "watchlist"
    return "low"
