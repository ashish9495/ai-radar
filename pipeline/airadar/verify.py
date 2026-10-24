"""Verification status from evidence we actually have. Never upgrades on model output alone."""
from __future__ import annotations

from .models import Source
from .normalize import registered_domain

OFFICIAL_DOMAINS = {
    "openai.com", "anthropic.com", "blog.google", "deepmind.google", "microsoft.com", "nvidia.com",
    "huggingface.co", "github.com", "meta.com", "mistral.ai", "aws.amazon.com", "amazon.com", "apple.com",
    "servicenow.com", "x.ai", "deepseek.com", "qwenlm.github.io", "ai.meta.com",
}


def verification_status(canonical_url: str, sighting_sources: list[Source], dtype: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (status, evidence[(url, kind)])."""
    evidence: list[tuple[str, str]] = []
    domain = registered_domain(canonical_url)
    official_source = any(s.is_official for s in sighting_sources)
    if official_source or domain in OFFICIAL_DOMAINS:
        kind = "repo" if domain == "github.com" else "official"
        evidence.append((canonical_url, kind))
        # A GitHub repo URL is the project's own primary source, but not proof of vendor claims.
        return ("official" if official_source or domain != "github.com" else "source_reported"), evidence
    independent = {s.id for s in sighting_sources}
    if len(independent) >= 2:
        return "multi_source", evidence
    if sighting_sources and max(s.reliability for s in sighting_sources) >= 3 and dtype != "discussion":
        return "source_reported", evidence
    return "unverified", evidence
