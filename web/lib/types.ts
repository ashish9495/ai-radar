export type DiscoveryType =
  | "news" | "tool" | "repo" | "model" | "paper" | "agent" | "workflow" | "discussion" | "dataset" | "other";
export type Verification = "unverified" | "source_reported" | "official" | "multi_source" | "disputed";
export type Importance = "must_know" | "worth_trying" | "experimental" | "watchlist" | "low";
export type Pricing = "free" | "freemium" | "paid" | "open_source" | "enterprise" | "unknown";
export type BookmarkStatus = "saved" | "tried" | "not_useful";

export interface DiscoveryRow {
  id: string;
  title: string;
  canonical_url: string;
  discovery_type: DiscoveryType;
  primary_category: string | null;
  published_at: string | null;
  first_discovered_at: string;
  last_verified_at: string | null;
  summary_short: string | null;
  why_it_matters: string | null;
  verification_status: Verification;
  importance: Importance;
  score: number;
  pricing: Pricing;
  is_open_source: boolean | null;
  license: string | null;
  stars: number | null;
  is_hidden_gem: boolean;
  source_names: string[];
  tags: string[];
  bookmark_status: BookmarkStatus | null;
  total_count: number;
}

export interface DiscoveryDetail extends Omit<DiscoveryRow, "source_names" | "tags" | "bookmark_status" | "total_count"> {
  released_at: string | null;
  updated_at_source: string | null;
  raw_excerpt: string | null;
  summary_detailed: string | null;
  practical_usefulness: string | null;
  known_limitations: string | null;
  claims_note: string | null;
  free_tier_notes: string | null;
  setup_requirements: string | null;
  hardware_requirements: string | null;
  security_notes: string | null;
  maintenance_signals: Record<string, unknown> | null;
  score_breakdown: Record<string, number | string>;
  model_used: string | null;
  extra: Record<string, unknown>;
  discovery_sources: { source_id: string; source_url: string; seen_at: string; sources: { name: string } | null }[];
  evidence_links: { url: string; kind: string; checked_at: string | null }[];
  discovery_tags: { tags: { name: string } | null }[];
}

export interface SearchParams {
  q?: string;
  types?: DiscoveryType[];
  category?: string;
  source?: string;
  pricing?: Pricing;
  openSource?: boolean;
  verification?: Verification;
  importance?: Importance;
  bookmark?: BookmarkStatus | "any";
  hiddenGems?: boolean;
  publishedFrom?: string;
  publishedTo?: string;
  discoveredFrom?: string;
  discoveredTo?: string;
  sort?: "discovered" | "published" | "score" | "relevance";
  limit?: number;
  offset?: number;
}

export interface PipelineStatus {
  last_collect_success: string | null;
  last_process_success: string | null;
  newest_discovery_at: string | null;
  discoveries_24h: number;
  pending_processing: number;
  failing_sources: number;
  delayed_sources: number;
  cost_today_usd: number;
  cost_month_usd: number;
}

export interface SourceWithHealth {
  id: string;
  name: string;
  adapter: string;
  enabled: boolean;
  interval_minutes: number;
  reliability: number;
  is_official: boolean;
  homepage: string | null;
  notes: string | null;
  source_health: {
    status: "unknown" | "healthy" | "delayed" | "failing" | "disabled";
    last_attempt_at: string | null;
    last_success_at: string | null;
    last_item_published_at: string | null;
    consecutive_failures: number;
    last_error: string | null;
  } | null;
}

export interface WorkflowRun {
  id: string;
  workflow: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  github_run_url: string | null;
  error: string | null;
  stats: Record<string, unknown>;
}

export interface PracticalWorkflow {
  id: string;
  slug: string;
  title: string;
  objective: string;
  tools_required: string[];
  setup: string | null;
  steps: string[];
  approx_cost: string | null;
  expected_result: string | null;
  limitations: string | null;
  security_notes: string | null;
  doc_links: string[];
  verified: boolean;
}

export interface Briefing {
  briefing_date: string;
  title: string;
  body_markdown: string;
  model_used: string | null;
  created_at: string;
}

export interface Category { slug: string; name: string; priority: number; enabled: boolean }
export interface Note { id: string; body: string; created_at: string }
