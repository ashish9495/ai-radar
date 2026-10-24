/** SAMPLE DATA — used only when the site is built without Supabase credentials, for UI development.
 * Every title is prefixed with [SAMPLE] and the app shows a banner. None of this is real news. */
import type { DiscoveryRow, PipelineStatus, SearchParams, SourceWithHealth, WorkflowRun } from "./types";

const h = (hoursAgo: number) => new Date(Date.now() - hoursAgo * 3600_000).toISOString();

function row(p: Partial<DiscoveryRow> & Pick<DiscoveryRow, "id" | "title" | "discovery_type">): DiscoveryRow {
  return {
    canonical_url: "https://example.com/sample", primary_category: null, published_at: h(5), first_discovered_at: h(4),
    last_verified_at: null, summary_short: "Sample summary for interface development only.", why_it_matters: null,
    verification_status: "source_reported", importance: "watchlist", score: 40, pricing: "unknown",
    is_open_source: null, license: null, stars: null, is_hidden_gem: false, source_names: ["Sample source"],
    tags: [], bookmark_status: null, total_count: 0, ...p,
  };
}

export const DEMO_DISCOVERIES: DiscoveryRow[] = [
  row({ id: "d1", title: "[SAMPLE] Vendor announces a new reasoning model API", discovery_type: "model",
        primary_category: "models", importance: "must_know", score: 78, verification_status: "official",
        why_it_matters: "Example of a Must Know item from an official source.", tags: ["Models", "API"] }),
  row({ id: "d2", title: "[SAMPLE] Open-source MCP server for helpdesk ticket lookup", discovery_type: "repo",
        primary_category: "it-support", importance: "worth_trying", score: 62, is_open_source: true, license: "MIT",
        stars: 340, is_hidden_gem: true, pricing: "open_source", tags: ["MCP", "ServiceNow"], published_at: h(30) }),
  row({ id: "d3", title: "[SAMPLE] Browser agent that fills repetitive web forms", discovery_type: "agent",
        primary_category: "agents", importance: "experimental", score: 51, verification_status: "unverified",
        tags: ["Agents", "Computer use"] }),
  row({ id: "d4", title: "[SAMPLE] Free AI meeting-notes tool launches", discovery_type: "tool",
        primary_category: "daily-tools", importance: "worth_trying", score: 58, pricing: "freemium", tags: ["Productivity"] }),
  row({ id: "d5", title: "[SAMPLE] Paper: benchmark for IT-ticket resolving agents", discovery_type: "paper",
        primary_category: "models", importance: "watchlist", score: 44, published_at: null, tags: ["Benchmark"] }),
  row({ id: "d6", title: "[SAMPLE] Discussion: how sysadmins use local LLMs", discovery_type: "discussion",
        primary_category: "it-support", importance: "watchlist", score: 38, verification_status: "unverified",
        published_at: h(200), first_discovered_at: h(2) }),
];

export function demoSearch(p: SearchParams): DiscoveryRow[] {
  let rows = DEMO_DISCOVERIES.filter((d) =>
    (!p.types?.length || p.types.includes(d.discovery_type)) &&
    (!p.category || d.primary_category === p.category) &&
    (!p.importance || d.importance === p.importance) &&
    (!p.verification || d.verification_status === p.verification) &&
    (!p.pricing || d.pricing === p.pricing) &&
    (p.openSource === undefined || d.is_open_source === p.openSource) &&
    (!p.hiddenGems || d.is_hidden_gem) &&
    (!p.bookmark || (p.bookmark === "any" ? d.bookmark_status : d.bookmark_status === p.bookmark)) &&
    (!p.q || `${d.title} ${d.summary_short}`.toLowerCase().includes(p.q.toLowerCase())));
  if (p.sort === "score") rows = [...rows].sort((a, b) => b.score - a.score);
  const total = rows.length;
  const off = Math.max(0, p.offset ?? 0);
  return rows.slice(off, off + (p.limit ?? 25)).map((r) => ({ ...r, total_count: total }));
}

export const DEMO_STATUS: PipelineStatus = {
  last_collect_success: h(0.4), last_process_success: h(0.3), newest_discovery_at: h(0.5), discoveries_24h: 6,
  pending_processing: 0, failing_sources: 1, delayed_sources: 0, cost_today_usd: 0.01, cost_month_usd: 0.2,
};

export const DEMO_SOURCES: SourceWithHealth[] = [
  { id: "sample-rss", name: "Sample RSS source", adapter: "rss", enabled: true, interval_minutes: 30, reliability: 5,
    is_official: true, homepage: null, notes: "Sample", source_health: { status: "healthy", last_attempt_at: h(0.4),
    last_success_at: h(0.4), last_item_published_at: h(3), consecutive_failures: 0, last_error: null } },
  { id: "sample-reddit", name: "Sample community source", adapter: "reddit", enabled: true, interval_minutes: 60,
    reliability: 2, is_official: false, homepage: null, notes: "Sample", source_health: { status: "failing",
    last_attempt_at: h(0.4), last_success_at: null, last_item_published_at: null, consecutive_failures: 4,
    last_error: "FetchError: HTTP 403 from https://www.reddit.com/r/x/top/.rss (sample)" } },
];

export const DEMO_RUNS: WorkflowRun[] = [
  { id: "r1", workflow: "collect", status: "partial", started_at: h(0.45), finished_at: h(0.4), github_run_url: null,
    error: "1 source(s) failed", stats: { items_new: 6, items_duplicate: 2 } },
];
