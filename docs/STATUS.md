# Build status — what is verified and what isn't (24 Oct 2026)

Built in a sandbox whose network allowed only npm/PyPI. Live sources, Supabase and GitHub were **not reachable**, so anything that needs them is marked unverified until it runs in your GitHub Actions.

| Requirement | Status | Evidence |
|---|---|---|
| Static Next.js build, all 12 routes, base path | ✅ verified | `next build` (static export) passes; 11 web unit tests |
| Responsive layout (desktop 1366 px, phone 390 px) | ✅ verified | headless-Chromium screenshots, no horizontal overflow, no console errors (demo mode) |
| Schema, migrations, RLS, search RPC | ✅ verified on PostgreSQL 18 with a Supabase auth stub | 6 RLS tests: anon blocked, non-members see 0 rows, bookmarks/notes private, owners can only toggle allowed columns, members can't write shared data |
| Collection logic for RSS, GitHub, HN, arXiv, Reddit; dedupe; idempotent re-runs; failed/empty/rate-limited sources | ✅ verified with **mocked** HTTP | 31 pipeline tests with recorded fixtures |
| Prompt-injection handling, output validation, budget stop | ✅ verified with a fake model | tests in `test_process.py` |
| No secrets in bundle or repo | ✅ verified | `scripts/check-secrets.mjs` on build output and tracked files |
| Real sources return data from GitHub Actions | ⏳ **unverified** | blocked here; run *Collect sources* and check Source health |
| Writes via Supabase REST API (PostgREST) | ⏳ **unverified against a live project** | request shapes unit-tested with mocks only |
| Magic-link auth on the deployed site | ⏳ **unverified** | needs your Supabase project + Pages URL |
| A real LLM provider's responses | ⏳ **unverified** | depends on which provider/model you configure |
| Scheduled workflows running on their own | ⏳ **unverified** | YAML validated; confirm in the Actions tab after the first schedule fires |
| Deployed dashboard reading real data | ⏳ **unverified** | final checklist in SETUP.md §5 |

Known limitations: X/Twitter, Quora and LinkedIn are not collected (see SOURCES.md); Reddit likely needs OAuth credentials; the fuzzy dedupe compares against the last 7 days only; the item page is `/item/?id=…` (query string) because static export can't pre-render unknown IDs.
