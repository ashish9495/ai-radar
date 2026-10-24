# Setup — from zero to a live private dashboard (~30–45 min)

You need: a GitHub account, a Supabase account (free tier is enough to start), and optionally an LLM API key.
Nothing here requires you to paste a secret into a chat or a file in the repo.

## 1. Create the GitHub repository
1. Create a **private** repository named `ai-radar` (any name works; the site path follows it).
2. Push this code:
   ```bash
   cd ai-radar
   git remote add origin https://github.com/<you>/ai-radar.git
   git push -u origin main
   ```
3. **GitHub Pages on a private repo requires a paid GitHub plan.** On the free plan, either make the repo public
   (safe: no secrets are in the code, and the data is protected by RLS, not by hiding the site) or use a separate public repo just for Pages.

## 2. Create the Supabase project
1. supabase.com → New project. Region close to you (e.g. Mumbai `ap-south-1`).
2. **Run the migrations** — SQL Editor → paste and run each file in order:
   `supabase/migrations/20261024000001_schema.sql`, `…0002_rls.sql`, `…0003_functions.sql`.
   (Or with the CLI: `supabase link --project-ref <ref>` then `supabase db push`.)
3. **Edit then run `supabase/seed.sql`** — change the email on line 4 to the address you will sign in with.
4. **Auth settings** (Authentication → Sign In / Providers):
   - Email provider: enabled. **Allow new users to sign up: OFF.**
   - Authentication → Users → *Add user* → *Send invitation* to your email (this is the only account).
   - Authentication → URL Configuration → Site URL: `https://<you>.github.io/ai-radar/`; add the same URL to Redirect URLs
     (add `http://localhost:3000/` too for local dev).
5. Project Settings → API Keys: note the **Project URL**, the **publishable key** (`sb_publishable_…`, browser-safe),
   and the **secret key** (`sb_secret_…`, or legacy `service_role`) — the secret one goes only into GitHub Secrets.

## 3. GitHub Actions secrets and variables
Repository → Settings → Secrets and variables → Actions.

**Secrets**
| Name | Value | Required |
|---|---|---|
| `SUPABASE_URL` | `https://<ref>.supabase.co` | yes |
| `SUPABASE_SERVICE_ROLE_KEY` | the **secret** key | yes |
| `LLM_API_KEY` | your model provider key | for AI summaries |
| `SEARCH_API_KEY` | Brave Search or Exa key | optional |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | a Reddit "script" app | optional, see SOURCES.md |

**Variables** (not secret)
| Name | Example | Notes |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://<ref>.supabase.co` | used at build time |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | `sb_publishable_…` | browser-safe because of RLS |
| `NEXT_PUBLIC_BASE_PATH` | `/ai-radar` | leave unset to use `/<repo-name>`; set to empty for a custom domain |
| `LLM_PROVIDER` | `openai_compatible` or `anthropic` | `none` = heuristic summaries only |
| `LLM_BASE_URL` | provider's OpenAI-compatible base URL | blank = provider default |
| `LLM_MODEL_FAST` / `LLM_MODEL_STRONG` | model ids from your provider | cheap model for routine items, stronger for high-score ones |
| `LLM_PRICE_INPUT_PER_M` / `LLM_PRICE_OUTPUT_PER_M` | from your provider's **official pricing page** | USD per 1M tokens; used for cost estimates and the budget stop |
| `DAILY_BUDGET_USD` | `0.50` | hard cap; the lower of this and the dashboard setting wins |
| `SEARCH_PROVIDER` | `brave` or `exa` | also enable the *Web search* source in Settings |

> ⚠️ If you leave the price variables at 0, the budget cap cannot work (every call is estimated at $0). Set them, and also set a spending limit in your provider's own console.

## 4. Enable Pages and run everything once
1. Settings → Pages → Source: **GitHub Actions**.
2. Actions tab → run, in order: **Tests**, **Deploy dashboard to GitHub Pages**, **Collect sources** (tick *force*), **Process discoveries**, **Daily briefing**.
3. Open `https://<you>.github.io/ai-radar/`, request a magic link, sign in. Settings → Source health shows which sources worked.

## 5. Verify it's really working (checklist)
- [ ] Tests workflow green (includes RLS tests on real Postgres and a secret scan of the built site)
- [ ] Collect run summary shows `success` or `partial` with `new=` > 0
- [ ] Settings page lists sources with *healthy*; failing ones show the actual error
- [ ] Signing in with a different email shows **Not authorised**
- [ ] In a private window, `https://<ref>.supabase.co/rest/v1/discoveries` with only the publishable key returns an error / no rows
- [ ] Next scheduled collect runs on its own within ~30–60 min (check the Actions tab — GitHub can delay schedules)

Troubleshooting: see [OPERATIONS.md](OPERATIONS.md).
