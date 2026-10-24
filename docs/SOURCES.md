# Sources and access limitations

AI RADAR uses only official APIs, RSS/Atom feeds and permitted public endpoints. It does **not** scrape sites that forbid it, and it does not claim to monitor everything on the internet.

| Source type | Method | Status / caveats |
|---|---|---|
| Vendor blogs (OpenAI, Google AI, DeepMind, Microsoft, AWS, NVIDIA, Hugging Face) | RSS | Feed URLs can change without notice — watch Source health |
| Microsoft 365 Roadmap | RSS | High volume, keyword-filtered |
| Independent / press (Simon Willison, The Verge, TechCrunch, BleepingComputer) | RSS | Press is secondary reporting → "Reported" unless an official source confirms |
| Product Hunt | RSS | Launch claims are self-reported; keyword-filtered |
| arXiv | Official API | Preprints, not peer reviewed; API asks for ≤1 request / 3 s (we make 1 per run) |
| Hacker News | Algolia HN Search API | Public, no key |
| GitHub releases + rising repos | REST API with the workflow's `GITHUB_TOKEN` | Search API is rate-limited (30 req/min authenticated); stars ≠ reliability |
| Hugging Face trending | Public Hub API | `sort=trendingScore` is undocumented-ish; if it breaks the source shows failing |
| Reddit | OAuth API if credentials set, else RSS | Unauthenticated requests from GitHub Actions IPs are frequently blocked (403/429). Create a "script" app at reddit.com/prefs/apps and review Reddit's Data API terms |
| Web search | Brave Search API or Exa (configurable) | Paid beyond free allowances; disabled until a key is set |

## Not included (and why)
- **X/Twitter** — the API's free tier no longer supports useful read access; paid tiers are expensive. No scraping.
- **YouTube** — possible via YouTube Data API v3 (free quota) or per-channel RSS (`https://www.youtube.com/feeds/videos.xml?channel_id=…`). Add channel feeds as `rss` sources if you want them.
- **Quora** — no public API; terms prohibit scraping. Not collected.
- **Anthropic** — no official RSS feed at time of writing; covered via HN, press and the web-search source.
- **LinkedIn** — no permitted API for this use.

New adapters go in `pipeline/airadar/adapters/` and are registered in `adapters/__init__.py`.
