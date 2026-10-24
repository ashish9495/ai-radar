"use client";
import { useEffect, useState } from "react";
import { getCategories, getSources } from "@/lib/api";
import { IMPORTANCE, PRICING_LABEL, TYPE_LABEL, VERIFICATION } from "@/lib/format";
import { useAsync, useDebounced } from "@/lib/hooks";
import type { DiscoveryType, Importance, Pricing, SearchParams, Verification } from "@/lib/types";

type Field = "q" | "type" | "category" | "source" | "pricing" | "openSource" | "verification" | "importance"
  | "bookmark" | "published" | "discovered" | "sort";

const toISO = (d: string, end = false) => (d ? new Date(`${d}T${end ? "23:59:59" : "00:00:00"}+05:30`).toISOString() : undefined);

export function Filters({ base, fields, onChange }: { base: SearchParams; fields: Field[]; onChange: (p: SearchParams) => void }) {
  const [q, setQ] = useState(base.q ?? "");
  const [f, setF] = useState<Record<string, string>>({});
  const dq = useDebounced(q, 350);
  const cats = useAsync(getCategories, []);
  const srcs = useAsync(getSources, []);
  const has = (x: Field) => fields.includes(x);

  useEffect(() => {
    const p: SearchParams = { ...base, q: dq || undefined };
    if (f.type) p.types = [f.type as DiscoveryType];
    if (f.category) p.category = f.category;
    if (f.source) p.source = f.source;
    if (f.pricing) p.pricing = f.pricing as Pricing;
    if (f.openSource) p.openSource = f.openSource === "yes";
    if (f.verification) p.verification = f.verification as Verification;
    if (f.importance) p.importance = f.importance as Importance;
    if (f.bookmark) p.bookmark = f.bookmark as SearchParams["bookmark"];
    if (f.pubFrom) p.publishedFrom = toISO(f.pubFrom);
    if (f.pubTo) p.publishedTo = toISO(f.pubTo, true);
    if (f.discFrom) p.discoveredFrom = toISO(f.discFrom);
    if (f.discTo) p.discoveredTo = toISO(f.discTo, true);
    if (f.sort) p.sort = f.sort as SearchParams["sort"];
    else if (dq) p.sort = "relevance";
    onChange(p);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dq, JSON.stringify(f)]);

  const sel = (key: string, label: string, opts: [string, string][]) => (
    <label className="flex flex-col gap-1 text-xs text-muted">
      {label}
      <select className="input" value={f[key] ?? ""} onChange={(e) => setF({ ...f, [key]: e.target.value })}>
        <option value="">Any</option>
        {opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
  const date = (key: string, label: string) => (
    <label className="flex flex-col gap-1 text-xs text-muted">{label}
      <input type="date" className="input" value={f[key] ?? ""} onChange={(e) => setF({ ...f, [key]: e.target.value })} />
    </label>
  );

  return (
    <div className="card mb-5 space-y-3">
      {has("q") && (
        <input type="search" className="input w-full" placeholder="Search titles and summaries… (supports “quotes” and -exclusions)"
          aria-label="Search" value={q} maxLength={200} onChange={(e) => setQ(e.target.value)} />
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {has("type") && sel("type", "Type", Object.entries(TYPE_LABEL))}
        {has("category") && sel("category", "Category", (cats.data ?? []).map((c) => [c.slug, c.name]))}
        {has("source") && sel("source", "Source", (srcs.data ?? []).map((s) => [s.id, s.name]))}
        {has("pricing") && sel("pricing", "Pricing", Object.entries(PRICING_LABEL))}
        {has("openSource") && sel("openSource", "Open source", [["yes", "Yes"], ["no", "No"]])}
        {has("verification") && sel("verification", "Verification", Object.entries(VERIFICATION).map(([k, v]) => [k, v.label]))}
        {has("importance") && sel("importance", "Importance", Object.entries(IMPORTANCE).map(([k, v]) => [k, v.label]))}
        {has("bookmark") && sel("bookmark", "My status", [["any", "Any saved"], ["saved", "Saved"], ["tried", "Tried"], ["not_useful", "Not useful"]])}
        {has("sort") && sel("sort", "Sort", [["discovered", "Newest discovered"], ["published", "Newest published"], ["score", "Highest score"], ["relevance", "Relevance"]])}
        {has("published") && <>{date("pubFrom", "Published from")}{date("pubTo", "Published to")}</>}
        {has("discovered") && <>{date("discFrom", "Discovered from")}{date("discTo", "Discovered to")}</>}
      </div>
      {Object.values(f).some(Boolean) && <button className="link text-xs" onClick={() => setF({})}>Clear filters</button>}
    </div>
  );
}
