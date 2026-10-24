"use client";
import Link from "next/link";
import { useState } from "react";
import { getReferences, searchDiscoveries, setBookmark } from "@/lib/api";
import { IMPORTANCE, PRICING_LABEL, TYPE_LABEL, VERIFICATION, formatIST, hostname, isOldNews, timeAgo } from "@/lib/format";
import { useAsync } from "@/lib/hooks";
import { useLive } from "./live";
import type { BookmarkStatus, DiscoveryRow, Reference, SearchParams } from "@/lib/types";
import { Badge, Empty, ErrorBox, ExtLink, Pager, Skeleton } from "./ui";

export function BookmarkButtons({ id, status, onChange }: { id: string; status: BookmarkStatus | null; onChange?: (s: BookmarkStatus | null) => void }) {
  const [cur, setCur] = useState(status);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const set = async (s: BookmarkStatus) => {
    const next = cur === s ? null : s;
    setBusy(true); setErr(null);
    try { await setBookmark(id, next); setCur(next); onChange?.(next); }
    catch (e) { setErr(e instanceof Error ? e.message : "Failed"); }
    finally { setBusy(false); }
  };
  const btn = (s: BookmarkStatus, label: string) => (
    <button type="button" disabled={busy} aria-pressed={cur === s} onClick={() => set(s)}
      className={`chip ${cur === s ? "chip-on" : ""}`}>{label}</button>
  );
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {btn("saved", cur === "saved" ? "★ Saved" : "☆ Save")}
      {btn("tried", "✓ Tried")}
      {btn("not_useful", "Not useful")}
      {err && <span className="text-xs text-red-300">{err}</span>}
    </div>
  );
}

export function DiscoveryCard({ d, compact = false, refs = [] }: { d: DiscoveryRow; compact?: boolean; refs?: Reference[] }) {
  const imp = IMPORTANCE[d.importance];
  const ver = VERIFICATION[d.verification_status];
  const old = isOldNews(d.published_at, d.first_discovered_at);
  return (
    <article className="card group">
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <Badge cls={imp.cls} title={`${imp.hint} · score ${d.score}`}>{imp.label}</Badge>
        <Badge cls={ver.cls} title={ver.hint}>{ver.label}</Badge>
        <Badge cls="badge-outline">{TYPE_LABEL[d.discovery_type]}</Badge>
        {d.is_hidden_gem && <Badge cls="badge-violet" title="Lesser-known project flagged as potentially useful">Hidden gem</Badge>}
        {old && <Badge cls="badge-muted" title="Published well before we discovered it">Newly discovered, not new</Badge>}
      </div>
      <h3 className="text-[15px] font-semibold leading-snug text-ink">
        <Link href={`/item/?id=${encodeURIComponent(d.id)}`} className="hover:text-accent">{d.title}</Link>
      </h3>
      {d.summary_short && <p className={`mt-1.5 text-sm text-ink/80 ${compact ? "line-clamp-2" : ""}`}>{d.summary_short}</p>}
      {!compact && d.why_it_matters && (
        <p className="mt-2 text-sm text-muted"><span className="font-medium text-accent">Why it matters:</span> {d.why_it_matters}</p>
      )}
      <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <div><dt className="inline">Published </dt><dd className="inline text-ink/70" title={formatIST(d.published_at)}>{d.published_at ? formatIST(d.published_at, false) : "date unknown"}</dd></div>
        <div><dt className="inline">Discovered </dt><dd className="inline text-ink/70" title={formatIST(d.first_discovered_at)}>{timeAgo(d.first_discovered_at)}</dd></div>
        <div><dt className="sr-only">Sources</dt><dd className="inline">{d.source_names.join(" · ") || "unknown source"}</dd></div>
        {d.stars != null && <div><dd className="inline" title="Stars measure popularity, not reliability">★ {d.stars.toLocaleString()}</dd></div>}
        {d.license && <div><dd className="inline">{d.license}</dd></div>}
        {d.pricing !== "unknown" && <div><dd className="inline">{PRICING_LABEL[d.pricing]}</dd></div>}
      </dl>
      {!compact && d.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">{d.tags.slice(0, 8).map((t) => <span key={t} className="tag">#{t}</span>)}</div>
      )}
      {refs.length > 0 && (
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span className="text-muted">References:</span>
          {refs.slice(0, 5).map((r) => (
            <ExtLink key={r.url} href={r.url} className={r.kind === "official" ? "font-medium" : ""}>{r.label} ↗</ExtLink>
          ))}
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-3">
        <ExtLink href={d.canonical_url} className="text-xs">Open · {hostname(d.canonical_url)} ↗</ExtLink>
        <BookmarkButtons id={d.id} status={d.bookmark_status} />
      </div>
    </article>
  );
}

/** Paginated, server-filtered list. All filtering happens in Postgres via search_discoveries(). */
export function DiscoveryFeed({ params, empty, pageSize = 20, compact = false, grid = true }:
  { params: SearchParams; empty?: string; pageSize?: number; compact?: boolean; grid?: boolean }) {
  const [offset, setOffset] = useState(0);
  const key = JSON.stringify(params);
  const [lastKey, setLastKey] = useState(key);
  if (key !== lastKey) { setLastKey(key); setOffset(0); }
  const { tick } = useLive();
  const { data, error, loading, reload } = useAsync(() => searchDiscoveries({ ...params, limit: pageSize, offset }), [key, offset, pageSize, tick]);
  const ids = (data ?? []).map((d) => d.id).join(",");
  const refs = useAsync(() => getReferences(ids ? ids.split(",") : []), [ids]);
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (loading && !data) return <Skeleton rows={3} />;
  if (!data?.length) return <Empty>{empty ?? "Nothing here yet. New items appear after the next collection run."}</Empty>;
  return (
    <div className={loading ? "opacity-60 transition-opacity" : ""}>
      <div className={grid ? "grid gap-3 lg:grid-cols-2" : "space-y-3"}>
        {data.map((d) => <DiscoveryCard key={d.id} d={d} compact={compact} refs={refs.data?.[d.id]} />)}
      </div>
      <Pager offset={offset} limit={pageSize} total={Number(data[0]?.total_count ?? 0)} onChange={setOffset} />
    </div>
  );
}
