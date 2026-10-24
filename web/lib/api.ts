import { DEMO_DISCOVERIES, DEMO_RUNS, DEMO_SOURCES, DEMO_STATUS, demoSearch } from "./demo";
import { IS_DEMO, supabase } from "./supabase";
import type {
  BookmarkStatus, Briefing, Category, DiscoveryDetail, DiscoveryRow, Note, PipelineStatus, PracticalWorkflow,
  SearchParams, SourceWithHealth, WorkflowRun,
} from "./types";

function unwrap<T>(res: { data: T | null; error: { message: string } | null }): T {
  if (res.error) throw new Error(res.error.message);
  return res.data as T;
}

/** Translate UI params into search_discoveries() RPC arguments (only set keys are sent). */
export function buildRpcArgs(p: SearchParams): Record<string, unknown> {
  const args: Record<string, unknown> = {
    p_sort: p.sort ?? "discovered",
    p_limit: Math.min(Math.max(p.limit ?? 25, 1), 100),
    p_offset: Math.max(p.offset ?? 0, 0),
  };
  const q = p.q?.trim().slice(0, 200);
  if (q) args.q = q;
  if (p.types?.length) args.p_types = p.types;
  if (p.category) args.p_category = p.category;
  if (p.source) args.p_source = p.source;
  if (p.pricing) args.p_pricing = p.pricing;
  if (p.openSource !== undefined) args.p_open_source = p.openSource;
  if (p.verification) args.p_verification = p.verification;
  if (p.importance) args.p_importance = p.importance;
  if (p.bookmark) args.p_bookmark_status = p.bookmark;
  if (p.hiddenGems) args.p_hidden_gems = true;
  if (p.publishedFrom) args.p_published_from = p.publishedFrom;
  if (p.publishedTo) args.p_published_to = p.publishedTo;
  if (p.discoveredFrom) args.p_discovered_from = p.discoveredFrom;
  if (p.discoveredTo) args.p_discovered_to = p.discoveredTo;
  return args;
}

export async function searchDiscoveries(p: SearchParams): Promise<DiscoveryRow[]> {
  if (IS_DEMO) return demoSearch(p);
  return unwrap(await supabase().rpc("search_discoveries", buildRpcArgs(p)));
}

export async function getPipelineStatus(): Promise<PipelineStatus> {
  if (IS_DEMO) return DEMO_STATUS;
  return unwrap(await supabase().from("v_pipeline_status").select("*").single());
}

export async function getTrending(): Promise<{ tag: string; recent_count: number; prior_count: number }[]> {
  if (IS_DEMO) return [{ tag: "MCP (sample)", recent_count: 4, prior_count: 1 }];
  return unwrap(await supabase().rpc("trending_tags", { p_days: 7, p_limit: 12 }));
}

export async function getSources(): Promise<SourceWithHealth[]> {
  if (IS_DEMO) return DEMO_SOURCES;
  // source_health is one-to-one (its PK is the FK), so PostgREST returns an object, not an array.
  const rows = unwrap(await supabase().from("sources")
    .select("id,name,adapter,enabled,interval_minutes,reliability,is_official,homepage,notes,source_health(*)")
    .order("name")) as unknown as SourceWithHealth[];
  return rows.map((r) => ({ ...r, source_health: Array.isArray(r.source_health) ? (r.source_health[0] ?? null) : r.source_health }));
}

export async function setSourceEnabled(id: string, enabled: boolean): Promise<void> {
  if (IS_DEMO) return;
  unwrap(await supabase().from("sources").update({ enabled }).eq("id", id).select("id"));
}

export async function setSourceInterval(id: string, minutes: number): Promise<void> {
  if (IS_DEMO) return;
  const m = Math.max(15, Math.min(1440, Math.round(minutes)));
  unwrap(await supabase().from("sources").update({ interval_minutes: m }).eq("id", id).select("id"));
}

export async function getCategories(): Promise<Category[]> {
  if (IS_DEMO) return [
    { slug: "models", name: "Models & research", priority: 8, enabled: true },
    { slug: "it-support", name: "IT support & ITSM", priority: 2, enabled: true },
    { slug: "agents", name: "Agents, MCP & automation", priority: 4, enabled: true },
  ];
  return unwrap(await supabase().from("categories").select("slug,name,priority,enabled").order("priority"));
}

export async function setCategoryEnabled(slug: string, enabled: boolean): Promise<void> {
  if (IS_DEMO) return;
  unwrap(await supabase().from("categories").update({ enabled }).eq("slug", slug).select("slug"));
}

export async function getWorkflowRuns(limit = 20): Promise<WorkflowRun[]> {
  if (IS_DEMO) return DEMO_RUNS;
  return unwrap(await supabase().from("workflow_runs").select("*").order("started_at", { ascending: false }).limit(limit));
}

export async function getFailedIngestion(limit = 15) {
  if (IS_DEMO) return [];
  return unwrap(await supabase().from("ingestion_runs")
    .select("id,source_id,started_at,status,error,items_fetched").in("status", ["failed", "partial"])
    .order("started_at", { ascending: false }).limit(limit)) as
    { id: string; source_id: string; started_at: string; status: string; error: string | null; items_fetched: number }[];
}

export async function getUsage() {
  if (IS_DEMO) return [];
  const since = new Date(Date.now() - 7 * 86400_000).toISOString();
  return unwrap(await supabase().from("api_usage").select("provider,model,purpose,input_tokens,output_tokens,est_cost_usd,created_at")
    .gte("created_at", since).order("created_at", { ascending: false }).limit(500)) as
    { provider: string; model: string; purpose: string; input_tokens: number; output_tokens: number; est_cost_usd: number; created_at: string }[];
}

export async function getSettings(): Promise<Record<string, unknown>> {
  if (IS_DEMO) return { daily_budget_usd: 0.5, summarize_min_score: 35 };
  const rows = unwrap(await supabase().from("app_settings").select("key,value")) as { key: string; value: unknown }[];
  return Object.fromEntries(rows.map((r) => [r.key, r.value]));
}

export async function setSetting(key: string, value: number): Promise<void> {
  if (IS_DEMO) return;
  if (!Number.isFinite(value) || value < 0 || value > 1000) throw new Error("Value out of range");
  unwrap(await supabase().from("app_settings").upsert({ key, value }).select("key"));
}

export async function getPracticalWorkflows(): Promise<PracticalWorkflow[]> {
  if (IS_DEMO) return [];
  return unwrap(await supabase().from("workflows").select("*").order("created_at", { ascending: false }));
}

export async function getLatestBriefing(): Promise<Briefing | null> {
  if (IS_DEMO) return { briefing_date: "sample", title: "Sample briefing", model_used: null, created_at: new Date().toISOString(),
    body_markdown: "## Must know\n- **[SAMPLE] Vendor announces a new reasoning model API** — demo text only." };
  const res = await supabase().from("briefings").select("*").order("briefing_date", { ascending: false }).limit(1);
  return (unwrap(res) as Briefing[])[0] ?? null;
}

export async function getDiscovery(id: string): Promise<DiscoveryDetail | null> {
  if (IS_DEMO) {
    const d = DEMO_DISCOVERIES.find((x) => x.id === id);
    return d ? ({ ...d, released_at: null, updated_at_source: null, raw_excerpt: "Sample excerpt.", summary_detailed: null,
      practical_usefulness: null, known_limitations: null, claims_note: null, free_tier_notes: null, setup_requirements: null,
      hardware_requirements: null, security_notes: null, maintenance_signals: null, score_breakdown: { method: "sample" },
      model_used: null, extra: {}, discovery_sources: [], evidence_links: [], discovery_tags: [] } as DiscoveryDetail) : null;
  }
  const res = await supabase().from("discoveries")
    .select("*,discovery_sources(source_id,source_url,seen_at,sources(name)),evidence_links(url,kind,checked_at),discovery_tags(tags(name))")
    .eq("id", id).maybeSingle();
  return unwrap(res) as DiscoveryDetail | null;
}

export async function setBookmark(discoveryId: string, status: BookmarkStatus | null): Promise<void> {
  if (IS_DEMO) return;
  const sb = supabase();
  if (status === null) {
    unwrap(await sb.from("bookmarks").delete().eq("discovery_id", discoveryId).select("discovery_id"));
  } else {
    unwrap(await sb.from("bookmarks").upsert({ discovery_id: discoveryId, status }, { onConflict: "user_id,discovery_id" })
      .select("discovery_id"));
  }
}

export async function getBookmark(discoveryId: string): Promise<BookmarkStatus | null> {
  if (IS_DEMO) return DEMO_DISCOVERIES.find((d) => d.id === discoveryId)?.bookmark_status ?? null;
  const rows = unwrap(await supabase().from("bookmarks").select("status").eq("discovery_id", discoveryId)) as { status: BookmarkStatus }[];
  return rows[0]?.status ?? null;
}

export async function getNotes(discoveryId: string): Promise<Note[]> {
  if (IS_DEMO) return [];
  return unwrap(await supabase().from("user_notes").select("id,body,created_at").eq("discovery_id", discoveryId)
    .order("created_at", { ascending: false }));
}

export async function addNote(discoveryId: string, body: string): Promise<void> {
  const text = body.trim();
  if (!text || text.length > 5000) throw new Error("Notes must be 1–5000 characters");
  if (IS_DEMO) return;
  unwrap(await supabase().from("user_notes").insert({ discovery_id: discoveryId, body: text }).select("id"));
}

export async function deleteNote(id: string): Promise<void> {
  if (IS_DEMO) return;
  unwrap(await supabase().from("user_notes").delete().eq("id", id).select("id"));
}
