from __future__ import annotations

import logging
import os
import re

from .config import Config
from .models import Category, Source
from .store import MemoryStore, Store, SupabaseStore


class RedactingFilter(logging.Filter):
    """Belt-and-braces: mask anything that looks like a credential before it reaches the log."""
    PATTERNS = [re.compile(p) for p in (
        r"sb_(secret|publishable)_[A-Za-z0-9_\-]+", r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",
        r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}", r"sk-[A-Za-z0-9_\-]{20,}",
        r"(?i)(api[_-]?key|token|secret)=([^&\s]+)")]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for p in self.PATTERNS:
            msg = p.sub("[REDACTED]", msg)
        record.msg, record.args = msg, ()
        return True


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%SZ"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    logging.getLogger("httpx").setLevel(logging.WARNING)


def build_store(config: Config, dry_run: bool = False) -> Store:
    if dry_run or not (config.supabase_url and config.supabase_service_key):
        if not dry_run:
            raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required (or pass --dry-run)")
        from .sync import load_config
        sources, categories = load_config()
        return MemoryStore([Source.from_row(s) for s in sources],
                           [Category.from_row(c) for c in categories], {})
    return SupabaseStore(config.supabase_url, config.supabase_service_key)
