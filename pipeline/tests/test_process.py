from airadar import briefing, collect, process
from airadar.llm import LLMResult, Provider, Summarizer, validate


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, data):
        self.data, self.calls = data, []

    def complete(self, system, user, model, max_tokens=900):
        self.calls.append(user)
        return LLMResult(self.data, model, 1000, 200)


def _collect(store, config, http):
    collect.run(store, config, http, force=True)


def test_processing_without_llm_uses_heuristics(store, config, http):
    _collect(store, config, http)
    result = process.run(store, config, http)
    assert result["processed"] == len(store.discoveries) and result["llm"] == 0
    oa = next(d for d in store.discoveries.values() if d["title"].startswith("Introducing a new reasoning"))
    assert oa["verification_status"] == "official"
    assert oa["importance"] in ("must_know", "worth_trying", "watchlist", "experimental")
    assert oa["score_breakdown"]["method"] == "heuristic"
    assert set(oa["score_breakdown"]) >= {"recency", "evidence", "usefulness", "relevance", "novelty", "cost"}
    ask = next(d for d in store.discoveries.values() if "helpdesk work" in d["title"])
    assert ask["verification_status"] == "unverified"
    assert "it-support" in store.cats[ask["id"]]


def test_llm_output_is_validated_and_sanitized(store, config, http, monkeypatch):
    _collect(store, config, http)
    malicious = {"summary_short": "A new model. See https://evil.example.com for more",
                 "summary_detailed": "Details", "why_it_matters": "Useful", "categories": ["models", "not-a-category"],
                 "tags": ["Reasoning"], "discovery_type": "model", "pricing": "free-forever-trust-me",
                 "usefulness_score": 99, "is_hidden_gem": False}
    fake = FakeProvider(malicious)
    monkeypatch.setattr(process, "build_provider", lambda c, h: fake)
    process.run(store, config, http)
    oa = next(d for d in store.discoveries.values() if d["title"].startswith("Introducing a new reasoning"))
    assert "evil.example.com" not in (oa["summary_short"] or "")
    assert oa["pricing"] != "free-forever-trust-me"
    assert "not-a-category" not in store.cats[oa["id"]]
    assert oa["score_breakdown"]["method"] == "llm"
    # Untrusted text is wrapped and the injection is passed only as data.
    assert any("<untrusted_source>" in c and "IGNORE PREVIOUS INSTRUCTIONS" in c for c in fake.calls)
    assert store.usage, "API usage must be logged"


def test_budget_stops_llm_but_still_processes(store, config, http, monkeypatch):
    _collect(store, config, http)
    store.settings["daily_budget_usd"] = "0.0001"
    monkeypatch.setenv("LLM_PRICE_INPUT_PER_M", "100")
    monkeypatch.setenv("LLM_PRICE_OUTPUT_PER_M", "100")
    from airadar.config import Config
    cfg = Config()
    fake = FakeProvider({"summary_short": "ok", "categories": [], "tags": []})
    monkeypatch.setattr(process, "build_provider", lambda c, h: fake)
    result = process.run(store, cfg, http)
    assert result["processed"] == len(store.discoveries)
    assert len(fake.calls) == 1  # first call spends the budget, the rest degrade gracefully
    assert result["budget_stopped"] >= 1


def test_validate_rejects_missing_summary():
    import pytest
    with pytest.raises(ValueError):
        validate({"summary_short": ""}, {"models"})


def test_briefing_template(store, config, http):
    _collect(store, config, http)
    process.run(store, config, http)
    res = briefing.run(store, config, http)
    body = next(iter(store.briefings.values()))["body_markdown"]
    assert res["items"] >= 1
    assert "https://openai.com/index/new-reasoning-model" in body
    assert body.startswith("# AI RADAR briefing")


def test_summarizer_unavailable_without_provider(store, config):
    assert not Summarizer(None, config, store, 1.0).available
