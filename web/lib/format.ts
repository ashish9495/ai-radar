import type { DiscoveryType, Importance, Pricing, Verification } from "./types";

const IST = "Asia/Kolkata";

/** ISO timestamp n days ago, rounded down to the hour so it is stable across renders. */
export function daysAgo(n: number, now: Date = new Date()): string {
  const t = now.getTime() - n * 86400_000;
  return new Date(t - (t % 3600_000)).toISOString();
}

export function formatIST(iso: string | null | undefined, withTime = true): string {
  if (!iso) return "Unknown";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Unknown";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: IST, day: "numeric", month: "short", year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit", hour12: false } : {}),
  }).format(d) + (withTime ? " IST" : "");
}

export function timeAgo(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "never";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "unknown";
  const s = Math.round((now.getTime() - t) / 1000);
  if (s < 0) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h} h ago`;
  return `${Math.round(h / 24)} days ago`;
}

/** Data freshness: never call stale data "live". */
export function freshness(iso: string | null | undefined, expectedMinutes = 60, now: Date = new Date()):
  "fresh" | "delayed" | "stale" | "none" {
  if (!iso) return "none";
  const ageMin = (now.getTime() - new Date(iso).getTime()) / 60000;
  if (ageMin <= expectedMinutes * 1.5) return "fresh";
  if (ageMin <= expectedMinutes * 6) return "delayed";
  return "stale";
}

/** True when the item was published long before we found it ("newly discovered", not "new"). */
export function isOldNews(published: string | null, discovered: string, thresholdHours = 72): boolean {
  if (!published) return false;
  return new Date(discovered).getTime() - new Date(published).getTime() > thresholdHours * 3600_000;
}

/** Only http(s) links are rendered; anything else (javascript:, data:) is dropped. */
export function safeHref(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.toString() : undefined;
  } catch {
    return undefined;
  }
}

export function hostname(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; }
}

export const IMPORTANCE: Record<Importance, { label: string; cls: string; hint: string }> = {
  must_know:    { label: "Must know",    cls: "badge-amber",  hint: "High score with reliable evidence" },
  worth_trying: { label: "Worth trying", cls: "badge-green",  hint: "Practical and reasonably verified" },
  experimental: { label: "Experimental", cls: "badge-violet", hint: "Promising but weakly verified or early" },
  watchlist:    { label: "Watchlist",    cls: "badge-slate",  hint: "Worth keeping an eye on" },
  low:          { label: "Low",          cls: "badge-muted",  hint: "Low relevance score" },
};

export const VERIFICATION: Record<Verification, { label: string; cls: string; hint: string }> = {
  official:        { label: "Official source",  cls: "badge-green",  hint: "From the vendor/project's own channel" },
  multi_source:    { label: "Multiple sources", cls: "badge-sky",    hint: "Reported by 2+ independent sources" },
  source_reported: { label: "Reported",         cls: "badge-slate",  hint: "Single reasonably reliable source" },
  unverified:      { label: "Unverified",       cls: "badge-muted",  hint: "Community post or low-reliability source" },
  disputed:        { label: "Disputed",         cls: "badge-red",    hint: "Conflicting information found" },
};

export const TYPE_LABEL: Record<DiscoveryType, string> = {
  news: "News", tool: "Tool", repo: "Repository", model: "Model", paper: "Paper", agent: "Agent",
  workflow: "Workflow", discussion: "Discussion", dataset: "Dataset", other: "Other",
};

export const PRICING_LABEL: Record<Pricing, string> = {
  free: "Free", freemium: "Freemium", paid: "Paid", open_source: "Open source", enterprise: "Enterprise", unknown: "Pricing unknown",
};
