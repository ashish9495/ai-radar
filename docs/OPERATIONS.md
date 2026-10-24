# Operations

## Schedules (targets, not guarantees)
| Workflow | Cron (UTC) | Effective |
|---|---|---|
| Collect sources | `7,37 * * * *` | every 30 min; each source runs only when its own interval (15 min–24 h, editable in Settings) is due |
| Process discoveries | after every collect + `52 * * * *` | verify, categorise, rank, summarise pending items |
| Daily briefing | `27 2 * * *` | ≈ 07:57 IST |
| Deploy | on push to `web/**` | rebuilds the static site (data is fetched live, so no redeploy is needed for new items) |

GitHub delays scheduled runs at busy times and **disables schedules after 60 days without repository activity** — Dependabot PRs or any push keep it alive; otherwise re-enable from the Actions tab. Free private repos get 2,000 Actions minutes/month; this setup uses roughly 1–2 minutes per collect run. Check your current quota in Settings → Billing.

## Monitoring
- **Dashboard → Settings & Health**: per-source status (`healthy` / `delayed` = > 3× interval since last success / `failing` = 3+ consecutive failures), last error, failed ingestion runs, workflow runs with links to the Actions logs, model usage and estimated cost.
- The top bar shows **data age** ("Collected 24 min ago · delayed/stale"). Nothing is ever labelled "live".
- Enable GitHub notifications for failed workflow runs (Settings → Notifications → Actions).

## Adding or changing sources
Edit `config/sources.json`, push. The next collect run syncs it. Fields `enabled`, `interval_minutes`, `notes` are owned by the dashboard after first insert (sync won't overwrite them). Sync refuses configs that look like they contain credentials. Adapter options:
- `rss`: `url`, `max_items`, `keyword_filter` (keep only AI/automation items — use for general feeds)
- `github_releases`: `repos`, `per_repo` · `github_search`: `queries`, `created_within_days`, `min_stars`
- `hackernews`: `queries`, `min_points`, `hours` · `reddit`: `subreddit`, `listing`, `t`, `limit`
- `huggingface`: `kind` (models|spaces|datasets), `sort`, `limit` · `arxiv`: `query`, `max_results`
- `web_search`: `queries`, `freshness_days`, `per_query` (needs `SEARCH_PROVIDER` + key)

## Adding practical workflows
Insert rows into `workflows` in the SQL editor (see the example in `seed.sql`). Set `verified = true` only after you've run it yourself.

## Costs (keep small)
- Free by default: RSS, GitHub API (`GITHUB_TOKEN`), HN Algolia API, arXiv, Hugging Face.
- Model calls happen only for items scoring ≥ `summarize_min_score` (default 35), at most `max_items_per_process_run` (60) per run, never twice for the same item (dedup happens before summarisation), and stop at the daily budget. Items processed without a model still get categories, tags, ranking and the source excerpt.
- Never assume a free tier lasts: check your provider's pricing page and set a spend limit there too.

## Backups
- Supabase free projects have no point-in-time recovery and **pause after ~1 week of inactivity** (the scheduled jobs keep it active). Weekly manual backup:
  `pg_dump "$DATABASE_URL" --schema=public --data-only -Fc > ai-radar-$(date +%F).dump` (connection string from Project Settings → Database).
- Bookmarks and notes are the only data you can't re-collect; discoveries can be rebuilt by re-running collection.

## Troubleshooting
| Symptom | Likely cause / fix |
|---|---|
| Site shows "Demo mode" banner | `NEXT_PUBLIC_SUPABASE_URL`/`…PUBLISHABLE_KEY` variables missing at build time → set them, re-run Deploy |
| Site loads but CSS/JS 404 | wrong base path → set `NEXT_PUBLIC_BASE_PATH` to `/<repo>` (or empty for custom domain) |
| Magic link opens a blank page / goes to localhost | Site URL / Redirect URLs in Supabase Auth don't include the Pages URL |
| "Not authorised" for your own email | email in `allowed_users` doesn't match exactly (stored lowercase) |
| "Signups not allowed" when requesting link | expected for unknown emails; for yours, invite the user first (Setup step 2.4) |
| Collect run fails on every source with 401 | wrong `SUPABASE_SERVICE_ROLE_KEY` (must be the secret key, not publishable) |
| Reddit sources failing with 403/429 | Reddit blocks cloud IPs; add Reddit OAuth credentials or disable those sources |
| No AI summaries ("method: heuristic") | `LLM_PROVIDER`/`LLM_MODEL_FAST`/`LLM_API_KEY` not set, or below score threshold |
| "method: budget…" on items | daily budget reached; raise it or wait until tomorrow (UTC) |
| Scheduled runs stopped | 60-day inactivity disable, or Actions minutes exhausted |
