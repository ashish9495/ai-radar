"""Runtime configuration from environment variables. Secrets never get logged."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))  # type: ignore[arg-type]
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    supabase_url: str | None = field(default_factory=lambda: _env("SUPABASE_URL"))
    supabase_service_key: str | None = field(repr=False, default_factory=lambda: _env("SUPABASE_SERVICE_ROLE_KEY"))

    github_token: str | None = field(repr=False, default_factory=lambda: _env("GH_API_TOKEN") or _env("GITHUB_TOKEN"))
    reddit_client_id: str | None = field(repr=False, default_factory=lambda: _env("REDDIT_CLIENT_ID"))
    reddit_client_secret: str | None = field(repr=False, default_factory=lambda: _env("REDDIT_CLIENT_SECRET"))

    search_provider: str = field(default_factory=lambda: (_env("SEARCH_PROVIDER", "none") or "none").lower())
    search_api_key: str | None = field(repr=False, default_factory=lambda: _env("SEARCH_API_KEY"))

    llm_provider: str = field(default_factory=lambda: (_env("LLM_PROVIDER", "none") or "none").lower())
    llm_base_url: str | None = field(default_factory=lambda: _env("LLM_BASE_URL"))
    llm_api_key: str | None = field(repr=False, default_factory=lambda: _env("LLM_API_KEY"))
    llm_model_fast: str | None = field(default_factory=lambda: _env("LLM_MODEL_FAST"))
    llm_model_strong: str | None = field(default_factory=lambda: _env("LLM_MODEL_STRONG") or _env("LLM_MODEL_FAST"))
    # USD per 1M tokens, used only for cost *estimates*. Set them from your provider's pricing page.
    llm_price_in_per_m: float = field(default_factory=lambda: _float("LLM_PRICE_INPUT_PER_M", 0.0))
    llm_price_out_per_m: float = field(default_factory=lambda: _float("LLM_PRICE_OUTPUT_PER_M", 0.0))
    daily_budget_usd_cap: float = field(default_factory=lambda: _float("DAILY_BUDGET_USD", 0.50))

    user_agent: str = field(default_factory=lambda: _env(
        "HTTP_USER_AGENT", "AI-RADAR/1.0 (personal research dashboard; +https://github.com)") or "AI-RADAR/1.0")
    github_run_id: str | None = field(default_factory=lambda: _env("GITHUB_RUN_ID"))
    github_run_url: str | None = field(default_factory=lambda: (
        f"{_env('GITHUB_SERVER_URL')}/{_env('GITHUB_REPOSITORY')}/actions/runs/{_env('GITHUB_RUN_ID')}"
        if _env("GITHUB_RUN_ID") and _env("GITHUB_REPOSITORY") else None))

    def status(self) -> dict[str, bool | str]:
        """Non-secret configuration status (booleans only for credentials)."""
        return {
            "supabase": bool(self.supabase_url and self.supabase_service_key),
            "github_token": bool(self.github_token),
            "reddit_oauth": bool(self.reddit_client_id and self.reddit_client_secret),
            "search_provider": self.search_provider if self.search_api_key else "none",
            "llm_provider": self.llm_provider if (self.llm_api_key or self.llm_provider == "none") else "misconfigured",
            "llm_model_fast": self.llm_model_fast or "",
            "llm_model_strong": self.llm_model_strong or "",
            "llm_pricing_set": bool(self.llm_price_in_per_m or self.llm_price_out_per_m),
        }
