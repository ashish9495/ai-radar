# AI RADAR

A private, continuously updated dashboard of useful AI developments — news, tools, open-source projects, agents, research — collected from real sources, deduplicated, ranked with an explainable score, and summarised with source links and verification status.

```
GitHub Actions (cron)                    Supabase (Postgres + Auth + RLS)          GitHub Pages (static)
┌──────────────────────────┐  service   ┌──────────────────────────────┐  RLS   ┌──────────────────────┐
│ collect  every 30 min    │──role key─▶│ discoveries, sources, health │◀──────│ Next.js static export│
│ process  after collect   │            │ bookmarks/notes (per user)   │ pub.  │ magic-link sign-in   │
│ briefing 08:00 IST       │            │ search_discoveries() RPC     │  key  │ 11 dashboard pages   │
└──────────────────────────┘            └──────────────────────────────┘        └──────────────────────┘
```

Pipeline: **DISCOVER → NORMALIZE → DEDUPLICATE → VERIFY → CATEGORIZE → RANK → SUMMARIZE → STORE → DISPLAY**

| Folder | What |
|---|---|
| `config/` | `sources.json` (21 sources, 8 adapter types) and `categories.json` — the single source of truth, synced to the DB on every run |
| `pipeline/` | Python 3.11+ package `airadar`: adapters, normalisation, dedupe, verification, ranking, pluggable LLM + search providers |
| `supabase/` | Migrations (schema, RLS, query functions), seed, and RLS tests that run against real PostgreSQL |
| `web/` | Next.js 16 + TypeScript + Tailwind 4, `output: "export"` (no server features) |
| `.github/workflows/` | tests, source-collection, discovery-processing, daily-briefing, deploy-pages |
| `docs/` | [SETUP.md](docs/SETUP.md) (start here), [OPERATIONS.md](docs/OPERATIONS.md), [SOURCES.md](docs/SOURCES.md), [STATUS.md](docs/STATUS.md) |

## Quick local checks

```bash
# pipeline tests (mocked HTTP, no network needed)
cd pipeline && python -m venv .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/pytest -q
# RLS tests against any throwaway Postgres
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres .venv/bin/pytest -q ../supabase/tests
# dashboard in demo mode (clearly labelled sample data)
cd ../web && npm ci && npm run dev
```

Full deployment: **[docs/SETUP.md](docs/SETUP.md)**.
