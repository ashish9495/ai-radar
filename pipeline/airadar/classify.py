"""Rule-based categorisation, tagging and type inference. Runs before (and without) any LLM,
so the pipeline still works when the model provider is unavailable or the budget is spent."""
from __future__ import annotations

import re
from collections import Counter

from .models import Category, RawItem

# Known entities → tag names. Matched on word boundaries, case-insensitive.
ENTITIES = {
    "openai": "OpenAI", "chatgpt": "ChatGPT", "gpt-5": "GPT-5", "gpt": "GPT", "codex": "Codex",
    "anthropic": "Anthropic", "claude": "Claude", "claude code": "Claude Code",
    "gemini": "Gemini", "deepmind": "DeepMind", "google": "Google",
    "llama": "Llama", "meta ai": "Meta AI", "mistral": "Mistral", "qwen": "Qwen", "deepseek": "DeepSeek",
    "microsoft": "Microsoft", "copilot": "Copilot", "azure": "Azure", "intune": "Intune", "entra": "Entra ID",
    "microsoft 365": "Microsoft 365", "teams": "Teams", "windows 11": "Windows 11", "powershell": "PowerShell",
    "servicenow": "ServiceNow", "jira": "Jira", "nvidia": "NVIDIA", "hugging face": "Hugging Face",
    "ollama": "Ollama", "llama.cpp": "llama.cpp", "vllm": "vLLM", "langchain": "LangChain", "n8n": "n8n",
    "mcp": "MCP", "model context protocol": "MCP", "cursor": "Cursor", "cline": "Cline", "browser-use": "browser-use",
    "playwright": "Playwright", "rag": "RAG", "fine-tuning": "Fine-tuning", "benchmark": "Benchmark",
    "open weights": "Open weights", "open-source": "Open source", "open source": "Open source",
    "self-hosted": "Self-hosted", "agent": "Agents", "agents": "Agents", "agentic": "Agents",
    "computer use": "Computer use", "voice": "Voice", "video generation": "Video generation",
    "image generation": "Image generation", "robotics": "Robotics", "cve": "CVE", "ransomware": "Ransomware",
    "prompt injection": "Prompt injection", "python": "Python", "typescript": "TypeScript", "api": "API",
}
_ENTITY_RES = [(re.compile(rf"(?<![\w-]){re.escape(k)}(?![\w-])", re.I), v) for k, v in ENTITIES.items()]

AI_TERMS = re.compile(r"\b(ai|a\.i\.|llm|llms|gpt|genai|machine learning|copilot|chatbot|agent|agents|agentic|"
                      r"automation|automate|mcp|model|neural|openai|anthropic|claude|gemini)\b", re.I)

TYPE_HINTS = [
    ("paper", re.compile(r"\b(arxiv|paper|preprint|we propose|we introduce)\b", re.I)),
    ("model", re.compile(r"\b(model release|new model|weights|checkpoint|\d+b parameters?|instruct model)\b", re.I)),
    ("agent", re.compile(r"\b(ai agent|agents?|agentic|computer[- ]use|browser automation|mcp server)\b", re.I)),
    ("tool", re.compile(r"\b(launch(es|ed)?|introducing|now available|new tool|app|extension|beta|general availability)\b", re.I)),
    ("workflow", re.compile(r"\b(how to|tutorial|guide|step[- ]by[- ]step|workflow)\b", re.I)),
]


def text_of(title: str, body: str | None) -> str:
    return f"{title}\n{body or ''}"


def keyword_filter_pass(item: RawItem, categories: list[Category]) -> bool:
    """For high-volume general sources: keep only items that look AI/automation related."""
    text = text_of(item.title, item.excerpt)
    return bool(AI_TERMS.search(text))


def categorize(title: str, body: str | None, categories: list[Category], default: str | None = None,
               max_cats: int = 3) -> list[str]:
    text = text_of(title, body).lower()
    title_l = title.lower()
    scores: Counter[str] = Counter()
    for cat in categories:
        if not cat.enabled:
            continue
        for kw in cat.keywords:
            pat = rf"(?<![\w-]){re.escape(kw.lower())}(?![\w-])"
            hits = len(re.findall(pat, text))
            if hits:
                scores[cat.slug] += hits + (2 if re.search(pat, title_l) else 0)
    ranked = [slug for slug, _ in scores.most_common(max_cats)]
    if default and default not in ranked:
        ranked = ranked[: max_cats - 1] + [default] if ranked else [default]
    return ranked


def extract_tags(title: str, body: str | None, extra_tags: list[str] | None = None, limit: int = 8) -> list[str]:
    text = text_of(title, (body or "")[:2000])
    found: list[str] = []
    for rx, name in _ENTITY_RES:
        if rx.search(text) and name not in found:
            found.append(name)
    for t in extra_tags or []:
        if t and len(t) <= 40 and t not in found:
            found.append(t)
    # "GPT" is redundant when a more specific tag exists
    if "GPT-5" in found and "GPT" in found:
        found.remove("GPT")
    return found[:limit]


def infer_type(current: str, title: str, body: str | None, adapter: str | None = None) -> str:
    if current not in ("news", "other", None):
        return current
    text = text_of(title, (body or "")[:1500])
    for dtype, rx in TYPE_HINTS:
        if rx.search(text):
            return dtype
    return current or "news"


PRICING_HINTS = [
    ("open_source", re.compile(r"\b(open[- ]source|mit licen[sc]e|apache[- ]2\.0|gpl)\b", re.I)),
    ("free", re.compile(r"\b(completely free|free to use|100% free)\b", re.I)),
    ("freemium", re.compile(r"\b(free tier|free plan|freemium|starts at \$|pro plan)\b", re.I)),
    ("enterprise", re.compile(r"\b(enterprise only|contact sales)\b", re.I)),
    ("paid", re.compile(r"\b(\$\d+(\.\d+)?\s*/\s*(mo|month|user))\b", re.I)),
]


def guess_pricing(title: str, body: str | None, license_: str | None) -> str:
    if license_:
        return "open_source"
    text = text_of(title, body)
    for label, rx in PRICING_HINTS:
        if rx.search(text):
            return label
    return "unknown"
