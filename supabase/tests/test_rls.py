"""Applies the real migrations + seed to a throwaway PostgreSQL database and checks the RLS policies.

Run:  DATABASE_URL=postgresql://postgres@localhost:5432/postgres python -m pytest supabase/tests
The database is dropped/recreated as `airadar_rls_test`. Requires psycopg (v3)."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
import psycopg.conninfo  # noqa: E402
ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not BASE_URL, reason="DATABASE_URL not set")

OWNER = {"id": str(uuid.uuid4()), "email": "work.ashishkothmeerkar@gmail.com"}
STRANGER = {"id": str(uuid.uuid4()), "email": "stranger@example.com"}


@pytest.fixture(scope="module")
def db():
    admin = psycopg.connect(BASE_URL, autocommit=True)
    admin.execute("drop database if exists airadar_rls_test")
    admin.execute("create database airadar_rls_test encoding 'UTF8' template template0")
    url = psycopg.conninfo.make_conninfo(BASE_URL, dbname="airadar_rls_test")
    conn = psycopg.connect(url, autocommit=True)
    conn.execute((ROOT / "supabase/tests/supabase_stub.sql").read_text())
    for f in sorted((ROOT / "supabase/migrations").glob("*.sql")):
        conn.execute(f.read_text())
    conn.execute((ROOT / "supabase/seed.sql").read_text())
    # minimal reference data + one discovery, inserted as the service role would
    cats = json.loads((ROOT / "config/categories.json").read_text())
    for c in cats:
        conn.execute("insert into categories (slug,name,priority,keywords) values (%s,%s,%s,%s)",
                     (c["slug"], c["name"], c["priority"], c["keywords"]))
    conn.execute("insert into sources (id,name,adapter,default_category) values ('s1','Source 1','rss','models')")
    conn.execute("insert into auth.users values (%s,%s),(%s,%s)", (OWNER["id"], OWNER["email"], STRANGER["id"], STRANGER["email"]))
    conn.execute("""insert into discoveries (id,title,normalized_title,canonical_url,url_hash,summary_short,importance,score)
                    values ('00000000-0000-0000-0000-000000000001','Ollama adds MCP support','ollama adds mcp support',
                            'https://ollama.com/blog/mcp','h1','Local agent tools','must_know',80)""")
    conn.execute("insert into discovery_sources (discovery_id,source_id,source_url) values ('00000000-0000-0000-0000-000000000001','s1','https://ollama.com/blog/mcp')")
    yield conn
    conn.close()
    admin.execute("drop database if exists airadar_rls_test")
    admin.close()


def as_user(conn, user: dict | None):
    conn.execute("reset role")
    if user is None:
        conn.execute("select set_config('request.jwt.claims', '', false)")
        conn.execute("set role anon")
    else:
        conn.execute("select set_config('request.jwt.claims', %s, false)",
                     (json.dumps({"sub": user["id"], "email": user["email"], "role": "authenticated"}),))
        conn.execute("set role authenticated")


def test_anon_cannot_read_anything(db):
    as_user(db, None)
    for table in ("discoveries", "sources", "bookmarks", "user_notes", "allowed_users", "api_usage"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(f"select * from {table} limit 1")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("select * from search_discoveries()")
    db.execute("reset role")


def test_non_member_sees_no_rows(db):
    as_user(db, STRANGER)
    assert db.execute("select count(*) from discoveries").fetchone()[0] == 0
    assert db.execute("select count(*) from sources").fetchone()[0] == 0
    assert db.execute("select count(*) from search_discoveries()").fetchone()[0] == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):  # RLS with-check violation
        db.execute("insert into bookmarks (user_id, discovery_id) values (%s, '00000000-0000-0000-0000-000000000001')",
                   (STRANGER["id"],))
    db.execute("reset role")


def test_owner_reads_and_searches(db):
    as_user(db, OWNER)
    assert db.execute("select count(*) from discoveries").fetchone()[0] == 1
    rows = db.execute("select title, source_names, total_count from search_discoveries(q => 'mcp')").fetchall()
    assert rows and rows[0][0] == "Ollama adds MCP support" and rows[0][1] == ["Source 1"] and rows[0][2] == 1
    assert db.execute("select count(*) from search_discoveries(q => 'kubernetes')").fetchone()[0] == 0
    db.execute("select * from v_pipeline_status").fetchone()
    db.execute("reset role")


def test_bookmarks_and_notes_are_private(db):
    as_user(db, OWNER)
    db.execute("insert into bookmarks (discovery_id, status) values ('00000000-0000-0000-0000-000000000001','tried')")
    db.execute("insert into user_notes (discovery_id, body) values ('00000000-0000-0000-0000-000000000001','works well')")
    assert db.execute("select bookmark_status from search_discoveries(p_bookmark_status => 'tried')").fetchone()[0] == 'tried'
    # cannot write rows for another user
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("insert into user_notes (user_id, discovery_id, body) values (%s,'00000000-0000-0000-0000-000000000001','x')",
                   (STRANGER["id"],))
    as_user(db, STRANGER)
    assert db.execute("select count(*) from bookmarks").fetchone()[0] == 0
    assert db.execute("select count(*) from user_notes").fetchone()[0] == 0
    db.execute("reset role")


def test_owner_can_toggle_sources_but_not_change_adapter_config(db):
    as_user(db, OWNER)
    db.execute("update sources set enabled = false where id = 's1'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("update sources set config = '{\"url\":\"https://evil\"}' where id = 's1'")
    db.execute("reset role")
    assert db.execute("select enabled from sources where id='s1'").fetchone()[0] is False


def test_member_cannot_write_discoveries(db):
    as_user(db, OWNER)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("update discoveries set title = 'x'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("delete from discoveries")
    db.execute("reset role")
