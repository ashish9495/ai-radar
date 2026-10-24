"use client";
import Link from "next/link";
import { DiscoveryFeed } from "@/components/discovery";
import { Badge, Empty, ErrorBox, FreshnessPill, Markdown, PageHeader, Section, Skeleton } from "@/components/ui";
import { getLatestBriefing, getPipelineStatus, getSources, getTrending } from "@/lib/api";
import { daysAgo, formatIST, timeAgo } from "@/lib/format";
import { useAsync } from "@/lib/hooks";

// Computed once per page load (rounded to the hour) so the queries stay stable between renders.
const D2 = daysAgo(2), D7 = daysAgo(7), D14 = daysAgo(14);

export default function Overview() {
  const status = useAsync(getPipelineStatus, []);
  const trending = useAsync(getTrending, []);
  const briefing = useAsync(getLatestBriefing, []);
  const sources = useAsync(getSources, []);
  const s = status.data;
  const failing = (sources.data ?? []).filter((x) => x.enabled && x.source_health && ["failing", "delayed"].includes(x.source_health.status));

  return (
    <>
      <PageHeader title="Overview" subtitle="What changed in AI that's useful to you — ranked, deduplicated and linked to the original sources.">
        {s && <FreshnessPill iso={s.newest_discovery_at} expectedMinutes={60} label="Newest item" />}
      </PageHeader>

      {status.error ? <ErrorBox error={status.error} onRetry={status.reload} /> : (
        <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4">
          <div className="stat"><div className="stat-n">{s?.discoveries_24h ?? "–"}</div><div className="stat-l">New discoveries (24 h)</div></div>
          <div className="stat"><div className="stat-n text-base sm:text-lg">{s ? timeAgo(s.last_collect_success) : "–"}</div>
            <div className="stat-l" title={formatIST(s?.last_collect_success)}>Last successful collection</div></div>
          <div className="stat"><div className={`stat-n ${s && s.failing_sources ? "text-red-300" : ""}`}>{s ? `${s.failing_sources} / ${s.delayed_sources}` : "–"}</div>
            <div className="stat-l">Failing / delayed sources</div></div>
          <div className="stat"><div className="stat-n">{s ? s.pending_processing : "–"}</div><div className="stat-l">Awaiting processing</div></div>
        </div>
      )}

      <div className="grid gap-8 xl:grid-cols-[1fr_320px]">
        <div className="min-w-0">
          <Section title="Must know · last 7 days">
            <DiscoveryFeed params={{ importance: "must_know", publishedFrom: D7, sort: "score" }} pageSize={6}
              empty="No Must Know items this week. That label requires a high score and reliable evidence." />
          </Section>
          <Section title="Try today" action={<Link href="/tools/" className="link text-xs">All tools →</Link>}>
            <DiscoveryFeed params={{ importance: "worth_trying", types: ["tool", "repo", "agent", "workflow"], publishedFrom: D14, sort: "score" }}
              pageSize={4} compact empty="No practical, reasonably verified tools found this week yet." />
          </Section>
          <Section title="Breaking · published in the last 48 hours" action={<Link href="/news/" className="link text-xs">All news →</Link>}>
            <DiscoveryFeed params={{ types: ["news", "model"], publishedFrom: D2, sort: "published" }} pageSize={6} compact />
          </Section>
          <Section title="Recently launched tools">
            <DiscoveryFeed params={{ types: ["tool"], publishedFrom: D14, sort: "published" }} pageSize={4} compact
              empty="No tool launches published in the last 14 days yet." />
          </Section>
          <Section title="Useful open-source projects" action={<Link href="/github/" className="link text-xs">More →</Link>}>
            <DiscoveryFeed params={{ types: ["repo"], publishedFrom: D14, sort: "published" }} pageSize={4} compact />
          </Section>
          <Section title="Latest · newest published first">
            <DiscoveryFeed params={{ publishedFrom: D7, sort: "published" }} pageSize={6} compact />
          </Section>
        </div>

        <aside className="min-w-0 space-y-8">
          <Section title="Daily briefing">
            {briefing.loading ? <Skeleton rows={1} /> : briefing.error ? <ErrorBox error={briefing.error} /> : briefing.data ? (
              <div className="card">
                <p className="mb-2 text-xs text-muted">{briefing.data.briefing_date} · {briefing.data.model_used ? `written by ${briefing.data.model_used}` : "template (no model)"}</p>
                <div className="max-h-[28rem] overflow-y-auto pr-1"><Markdown md={briefing.data.body_markdown} /></div>
              </div>
            ) : <Empty>No briefing yet. It is generated daily at 08:00 IST.</Empty>}
          </Section>
          <Section title="Trending tags · 7 days">
            {trending.error ? <ErrorBox error={trending.error} /> : !trending.data?.length ? (
              <Empty>Not enough data yet. A tag needs at least 2 items this week to trend.</Empty>
            ) : (
              <ul className="card space-y-1.5 text-sm">
                {trending.data.map((t) => (
                  <li key={t.tag} className="flex items-center justify-between gap-2">
                    <span>#{t.tag}</span>
                    <span className="font-mono text-xs text-muted" title={`${t.recent_count} this week vs ${t.prior_count} the week before`}>
                      {t.recent_count} <span className={t.recent_count > t.prior_count ? "text-accent" : ""}>{t.recent_count > t.prior_count ? "▲" : t.recent_count < t.prior_count ? "▼" : "·"}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section title="Source health" action={<Link href="/settings/" className="link text-xs">Details →</Link>}>
            {sources.error ? <ErrorBox error={sources.error} /> : !failing.length ? (
              <div className="card text-sm text-muted">{sources.data ? "All enabled sources are reporting normally." : "Loading…"}</div>
            ) : (
              <ul className="card space-y-2 text-sm">
                {failing.map((x) => (
                  <li key={x.id}>
                    <div className="flex items-center justify-between gap-2"><span>{x.name}</span>
                      <Badge cls={x.source_health!.status === "failing" ? "badge-red" : "badge-amber"}>{x.source_health!.status}</Badge></div>
                    <p className="truncate text-xs text-muted" title={x.source_health!.last_error ?? ""}>
                      last OK {timeAgo(x.source_health!.last_success_at)}{x.source_health!.last_error ? ` · ${x.source_health!.last_error}` : ""}</p>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </aside>
      </div>
    </>
  );
}
