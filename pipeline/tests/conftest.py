"""Shared fixtures. All HTTP is served by httpx.MockTransport from recorded fixtures — these are
MOCKED tests; they verify our parsing and pipeline logic, not the live availability of any source."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from airadar.config import Config
from airadar.http import Http
from airadar.models import Category, Source
from airadar.store import MemoryStore
from airadar.sync import load_config

FIX = Path(__file__).parent / "fixtures"


def fixture_bytes(name: str) -> bytes:
    return (FIX / name).read_bytes()


class Router:
    """Maps URL substrings to responses and records requests."""

    def __init__(self):
        self.routes: list[tuple[str, int, bytes, dict]] = []
        self.calls: list[httpx.Request] = []

    def add(self, contains: str, body: bytes | str | dict | list, status: int = 200, headers: dict | None = None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.routes.append((contains, status, body, headers or {}))

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        url = str(request.url)
        for contains, status, body, headers in self.routes:
            if contains in url:
                return httpx.Response(status, content=body, headers=headers)
        return httpx.Response(404, content=b"not mocked")


@pytest.fixture
def router() -> Router:
    r = Router()
    r.add("openai.com/news/rss.xml", fixture_bytes("openai_rss.xml"))
    r.add("hn.algolia.com", fixture_bytes("hn.json"))
    r.add("/repos/ollama/ollama/releases", fixture_bytes("gh_releases.json"))
    r.add("/repos/ollama/ollama", fixture_bytes("gh_repo.json"))
    r.add("export.arxiv.org", fixture_bytes("arxiv.xml"))
    r.add("reddit.com", "blocked", status=403)
    return r


@pytest.fixture
def http(router) -> Http:
    return Http("test-agent", transport=httpx.MockTransport(router.handler), sleep=lambda s: None, max_retries=1)


@pytest.fixture
def categories() -> list[Category]:
    _, cats = load_config()
    return [Category.from_row(c) for c in cats]


@pytest.fixture
def sources() -> list[Source]:
    return [
        Source("openai-news", "OpenAI News", "rss", {"url": "https://openai.com/news/rss.xml"}, 5, True, True, 30, "models"),
        Source("hn-ai", "Hacker News (AI)", "hackernews", {"queries": ["LLM"], "min_points": 40}, 3, False, True, 30, "coding"),
        Source("gh-releases", "GitHub releases", "github_releases", {"repos": ["ollama/ollama"]}, 4, True, True, 30, "open-source"),
        Source("arxiv-ai", "arXiv", "arxiv", {"query": "cat:cs.AI"}, 4, False, True, 180, "models"),
        Source("reddit-localllama", "r/LocalLLaMA", "reddit", {"subreddit": "LocalLLaMA"}, 2, False, True, 60, "open-source"),
        Source("web-search", "Web search", "web_search", {"queries": ["x"]}, 2, False, True, 180, None),
    ]


@pytest.fixture
def store(sources, categories) -> MemoryStore:
    return MemoryStore(sources, categories, {"daily_budget_usd": "0.50"})


@pytest.fixture
def config(monkeypatch) -> Config:
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "LLM_PROVIDER", "LLM_API_KEY", "SEARCH_PROVIDER",
              "SEARCH_API_KEY", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "GITHUB_TOKEN", "GH_API_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    return Config()
