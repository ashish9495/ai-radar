"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { BookmarkButtons } from "@/components/discovery";
import { Badge, Empty, ErrorBox, ExtLink, PageHeader, Section, Skeleton } from "@/components/ui";
import { addNote, deleteNote, getBookmark, getDiscovery, getNotes } from "@/lib/api";
import { IMPORTANCE, PRICING_LABEL, TYPE_LABEL, VERIFICATION, formatIST, hostname, isOldNews } from "@/lib/format";
import { useAsync } from "@/lib/hooks";

export default function ItemPage() {
  return <Suspense fallback={<Skeleton />}><Item /></Suspense>;
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  if (v === null || v === undefined || v === "") return null;
  return <div className="grid grid-cols-[150px_1fr] gap-2 border-b border-line/50 py-1.5 text-sm"><dt className="text-muted">{k}</dt><dd className="break-words">{v}</dd></div>;
}

function Item() {
  const id = useSearchParams().get("id") ?? "";
  const { data: d, error, loading, reload } = useAsync(() => getDiscovery(id), [id]);
  const bm = useAsync(() => getBookmark(id), [id]);
  if (!id) return <Empty>No item selected.</Empty>;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (loading) return <Skeleton />;
  if (!d) return <Empty>This item doesn&apos;t exist or you don&apos;t have access to it.</Empty>;

  const imp = IMPORTANCE[d.importance], ver = VERIFICATION[d.verification_status];
  const ms = d.maintenance_signals ?? {};
  const breakdown = Object.entries(d.score_breakdown ?? {}).filter(([k]) => k !== "method");
  return (
    <>
      <div className="mb-3 flex flex-wrap gap-1.5">
        <Badge cls={imp.cls} title={imp.hint}>{imp.label}</Badge>
        <Badge cls={ver.cls} title={ver.hint}>{ver.label}</Badge>
        <Badge cls="badge-outline">{TYPE_LABEL[d.discovery_type]}</Badge>
        {d.is_hidden_gem && <Badge cls="badge-violet">Hidden gem</Badge>}
        {isOldNews(d.published_at, d.first_discovered_at) && <Badge cls="badge-muted">Newly discovered, not newly published</Badge>}
      </div>
      <PageHeader title={d.title}>
        <ExtLink href={d.canonical_url} className="btn">Open original · {hostname(d.canonical_url)} ↗</ExtLink>
      </PageHeader>

      <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0 space-y-6">
          {d.summary_short && <p className="text-base text-ink/90">{d.summary_short}</p>}
          {d.summary_detailed && <p className="text-sm leading-relaxed text-ink/80">{d.summary_detailed}</p>}
          <dl>
            <Row k="Why it matters" v={d.why_it_matters} />
            <Row k="Practical use" v={d.practical_usefulness} />
            <Row k="Known limitations" v={d.known_limitations} />
            <Row k="Claims note" v={d.claims_note} />
            <Row k="Setup" v={d.setup_requirements} />
            <Row k="Hardware" v={d.hardware_requirements} />
            <Row k="Security" v={d.security_notes} />
            <Row k="Pricing" v={d.pricing !== "unknown" ? PRICING_LABEL[d.pricing] : "Not stated by sources"} />
            <Row k="Free tier" v={d.free_tier_notes} />
            <Row k="Licence" v={d.license} />
            <Row k="Stars" v={d.stars != null ? `${d.stars.toLocaleString()} (popularity, not a reliability signal)` : null} />
            <Row k="Last push" v={ms.pushed_at ? formatIST(String(ms.pushed_at)) : null} />
            <Row k="Open issues" v={ms.open_issues_count != null ? String(ms.open_issues_count) : null} />
            <Row k="Archived" v={ms.archived ? "Yes — no longer maintained" : null} />
          </dl>
          {!d.why_it_matters && !d.summary_detailed && (
            <p className="text-xs text-muted">No AI analysis for this item (below the summary threshold, budget reached, or no model configured). The summary above is the source&apos;s own excerpt.</p>
          )}
          {d.raw_excerpt && (
            <Section title="Source excerpt (untrusted text, shown as-is)">
              <p className="card whitespace-pre-line text-sm text-muted">{d.raw_excerpt}</p>
            </Section>
          )}
          <Notes id={d.id} />
        </div>

        <aside className="space-y-6">
          <div className="card space-y-3">
            {bm.loading ? <p className="text-xs text-muted">Loading status…</p> : <BookmarkButtons key={bm.data ?? "none"} id={d.id} status={bm.data ?? null} />}
            <p className="text-xs text-muted">Tap a status again to clear it.</p>
          </div>
          <Section title="Timeline (IST)">
            <dl className="card">
              <Row k="Published" v={d.published_at ? formatIST(d.published_at) : "Unknown"} />
              <Row k="Released" v={d.released_at ? formatIST(d.released_at) : null} />
              <Row k="Updated at source" v={d.updated_at_source ? formatIST(d.updated_at_source) : null} />
              <Row k="First discovered" v={formatIST(d.first_discovered_at)} />
              <Row k="Last verified" v={d.last_verified_at ? formatIST(d.last_verified_at) : "Not verified"} />
            </dl>
          </Section>
          <Section title="Seen in">
            <ul className="card space-y-1.5 text-sm">
              {d.discovery_sources.map((s) => (
                <li key={s.source_id + s.source_url}><ExtLink href={s.source_url}>{s.sources?.name ?? s.source_id} ↗</ExtLink></li>
              ))}
            </ul>
          </Section>
          {d.evidence_links.length > 0 && (
            <Section title="Evidence">
              <ul className="card space-y-1.5 text-sm">{d.evidence_links.map((e) => <li key={e.url}><Badge cls="badge-outline">{e.kind}</Badge> <ExtLink href={e.url}>{hostname(e.url)} ↗</ExtLink></li>)}</ul>
            </Section>
          )}
          <Section title={`Score ${d.score}`}>
            <div className="card space-y-1.5 text-xs">
              {breakdown.map(([k, v]) => (
                <div key={k}><div className="flex justify-between"><span className="text-muted">{k}</span><span className="font-mono">{String(v)}</span></div>
                  <div className="h-1 rounded bg-panel2"><div className="h-1 rounded bg-accent" style={{ width: `${Math.min(100, (Number(v) / 25) * 100)}%` }} /></div></div>
              ))}
              <p className="pt-1 text-muted">Method: {String(d.score_breakdown?.method ?? "–")}{d.model_used ? ` · ${d.model_used}` : ""}</p>
            </div>
          </Section>
          {d.discovery_tags.length > 0 && (
            <div className="flex flex-wrap gap-1">{d.discovery_tags.map((t) => t.tags && <span key={t.tags.name} className="tag">#{t.tags.name}</span>)}</div>
          )}
        </aside>
      </div>
    </>
  );
}

function Notes({ id }: { id: string }) {
  const notes = useAsync(() => getNotes(id), [id]);
  const [text, setText] = useState("");
  const [err, setErr] = useState<string | null>(null);
  return (
    <Section title="My notes (private)">
      <form className="mb-3 flex flex-col gap-2" onSubmit={async (e) => {
        e.preventDefault(); setErr(null);
        try { await addNote(id, text); setText(""); notes.reload(); } catch (x) { setErr(x instanceof Error ? x.message : "Failed"); }
      }}>
        <textarea className="input min-h-20" maxLength={5000} value={text} onChange={(e) => setText(e.target.value)}
          placeholder="What did you try? Did it work?" aria-label="New note" />
        <div className="flex items-center gap-2"><button className="btn" disabled={!text.trim()}>Add note</button>{err && <span className="text-xs text-red-300">{err}</span>}</div>
      </form>
      {notes.data?.length ? (
        <ul className="space-y-2">{notes.data.map((n) => (
          <li key={n.id} className="card text-sm"><p className="whitespace-pre-line">{n.body}</p>
            <div className="mt-2 flex justify-between text-xs text-muted"><span>{formatIST(n.created_at)}</span>
              <button className="link" onClick={async () => { await deleteNote(n.id); notes.reload(); }}>Delete</button></div></li>))}</ul>
      ) : <p className="text-xs text-muted">No notes yet.</p>}
    </Section>
  );
}
