"use client";
import type { ReactNode } from "react";
import { freshness, formatIST, safeHref, timeAgo } from "@/lib/format";
import { parseMarkdown, type Inline } from "@/lib/markdown";

export function Badge({ cls = "badge-slate", children, title }: { cls?: string; children: ReactNode; title?: string }) {
  return <span className={`badge ${cls}`} title={title}>{children}</span>;
}

export function ExtLink({ href, children, className = "" }: { href: string | null | undefined; children: ReactNode; className?: string }) {
  const safe = safeHref(href);
  if (!safe) return <span className={className}>{children}</span>;
  return <a href={safe} target="_blank" rel="noopener noreferrer nofollow" className={`link ${className}`}>{children}</a>;
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-muted">{subtitle}</p>}
      </div>
      {children}
    </header>
  );
}

export function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="mb-8">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="section-title">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-dashed border-line p-6 text-center text-sm text-muted">{children}</div>;
}

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
      <p className="font-medium">Couldn&apos;t load this data.</p>
      <p className="mt-1 break-words text-red-300/80">{error}</p>
      {onRetry && <button onClick={onRetry} className="btn mt-3">Retry</button>}
    </div>
  );
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => <div key={i} className="h-24 animate-pulse rounded-lg bg-panel" />)}
    </div>
  );
}

/** Shows data age honestly — "Live" is never claimed, only how old the data is. */
export function FreshnessPill({ iso, expectedMinutes = 60, label = "Updated" }: { iso: string | null | undefined; expectedMinutes?: number; label?: string }) {
  const f = freshness(iso, expectedMinutes);
  const cls = { fresh: "badge-green", delayed: "badge-amber", stale: "badge-red", none: "badge-muted" }[f];
  const word = { fresh: "", delayed: " · delayed", stale: " · stale", none: "" }[f];
  return (
    <Badge cls={cls} title={iso ? formatIST(iso) : "No successful run recorded"}>
      <span className={`dot ${f === "fresh" ? "dot-pulse" : ""}`} />
      {iso ? `${label} ${timeAgo(iso)}${word}` : `${label}: never`}
    </Badge>
  );
}

export function Pager({ offset, limit, total, onChange }: { offset: number; limit: number; total: number; onChange: (o: number) => void }) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return (
    <nav className="mt-4 flex items-center justify-between text-sm text-muted" aria-label="Pagination">
      <button className="btn" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>← Previous</button>
      <span>Page {page} of {pages} · {total} items</span>
      <button className="btn" disabled={page >= pages} onClick={() => onChange(offset + limit)}>Next →</button>
    </nav>
  );
}

function InlineView({ c }: { c: Inline[] }) {
  return <>{c.map((t, i) => {
    switch (t.t) {
      case "b": return <strong key={i}>{t.v}</strong>;
      case "i": return <em key={i}>{t.v}</em>;
      case "code": return <code key={i} className="rounded bg-panel px-1 text-xs">{t.v}</code>;
      case "a": return <ExtLink key={i} href={t.href}>{t.v}</ExtLink>;
      default: return <span key={i}>{t.v}</span>;
    }
  })}</>;
}

export function Markdown({ md }: { md: string }) {
  return (
    <div className="space-y-2 text-sm leading-relaxed text-ink/90">
      {parseMarkdown(md).map((b, i) =>
        b.t === "h" ? (b.level === 1 ? <h3 key={i} className="text-base font-semibold"><InlineView c={b.c} /></h3>
                     : <h4 key={i} className="pt-2 text-xs font-semibold uppercase tracking-wider text-accent"><InlineView c={b.c} /></h4>)
        : b.t === "li" ? <p key={i} className="pl-4 -indent-4">• <InlineView c={b.c} /></p>
        : <p key={i}><InlineView c={b.c} /></p>)}
    </div>
  );
}
