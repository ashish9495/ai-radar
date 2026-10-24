import logging

import httpx
import pytest

from airadar.cli import RedactingFilter
from airadar.http import FetchError, Http
from airadar.store import SupabaseStore
from airadar.sync import load_config, validate


def test_config_files_are_valid():
    sources, categories = load_config()
    assert len(sources) >= 10 and len({s["adapter"] for s in sources}) >= 6


def test_sync_rejects_credentials_in_source_config():
    _, cats = load_config()
    bad = [{"id": "x", "name": "x", "adapter": "rss", "config": {"url": "u", "api_key": "123"}}]
    with pytest.raises(ValueError):
        validate(bad, cats)


def test_log_redaction():
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "key sb_" + "secret_abcdef123456 and ghp_%s url?api_key=zzz",
                            ("a" * 30,), None)
    RedactingFilter().filter(rec)
    msg = rec.getMessage()
    assert "sb_secret_" not in msg and "ghp_" not in msg and "zzz" not in msg


def test_http_error_messages_drop_query_strings():
    h = Http("t", transport=httpx.MockTransport(lambda r: httpx.Response(500)), sleep=lambda s: None, max_retries=0)
    with pytest.raises(FetchError) as e:
        h.get("https://api.example.com/x?api_key=SECRET")
    assert "SECRET" not in str(e.value)


def test_supabase_store_headers_for_new_secret_keys():
    seen = {}

    def handler(req):
        seen.update(req.headers)
        return httpx.Response(200, json=[])

    SupabaseStore("https://x.supabase.co", "sb_secret_test", transport=httpx.MockTransport(handler)).list_sources()
    assert seen["apikey"] == "sb_secret_test" and "authorization" not in seen


def test_supabase_store_insert_is_idempotent_and_index_pages():
    calls = []

    def handler(req):
        calls.append(req)
        if req.method == "POST" and req.url.path.endswith("/discoveries"):
            assert "on_conflict=url_hash" in str(req.url) and "ignore-duplicates" in req.headers["prefer"]
            return httpx.Response(201, json=[])            # duplicate ignored by Postgres
        if req.method == "GET" and "url_hash=eq.h1" in str(req.url):
            return httpx.Response(200, json=[{"id": "existing", "url_hash": "h1"}])
        if req.method == "GET":
            off = int(req.url.params.get("offset", "0"))
            n = 1000 if off == 0 else 3
            return httpx.Response(200, json=[{"id": f"{off + i}"} for i in range(n)])
        return httpx.Response(500)

    st = SupabaseStore("https://x.supabase.co", "legacy.jwt.key", transport=httpx.MockTransport(handler))
    assert st.insert_discovery({"url_hash": "h1", "title": "t"}) == "existing"
    assert len(st.recent_index(7)) == 1003
