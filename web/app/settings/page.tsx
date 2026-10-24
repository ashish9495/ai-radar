"use client";
import { useMemo, useState } from "react";
import { useAuth } from "@/components/auth";
import { Badge, Empty, ErrorBox, ExtLink, PageHeader, Section, Skeleton } from "@/components/ui";
import {
  getCategories, getFailedIngestion, getPipelineStatus, getSettings, getSources, getUsage, getWorkflowRuns,
  setCategoryEnabled, setSetting, setSourceEnabled,
} from "@/lib/api";
import { formatIST, timeAgo } from "@/lib/format";
import { useAsync } from "@/lib/hooks";

const HEALTH_CLS: Record<string, string> = { healthy: "badge-green", delayed: "badge-amber", failing: "badge-red", disabled: "badge-muted", unknown: "badge-muted" };

export default function Settings() {
  const auth = useAuth();
  const sources = useAsync(getSources, []);
  const cats = useAsync(getCategories, []);
  const runs = useAsync(() => getWorkflowRuns(25), []);
  const failed = useAsync(() => getFailedIngestion(15), []);
  const usage = useAsync(getUsage, []);
  const settings = useAsync(getSettings, []);
  const status = useAsync(getPipelineStatus, []);
  const [msg, setMsg] = useState<string | null>(null);

  const act = async (fn: () => Promise<void>, ok: string, reload: () => void) => {
    setMsg(null);
    try { await fn(); setMsg(ok); reload(); } catch (e) { setMsg(`Error: ${e instanceof Error ? e.message : e}`); }
  };

  // Non-secret provider status is written by the pipeline into each run's stats (booleans only).
  const providerStatus = useMemo(() => {
    const r = runs.data?.find((x) => x.stats && typeof x.stats === "object" && "config" in x.stats);
    return (r?.stats.config ?? null) as Record<string, string | boolean> | null;
  }, [runs.data]);

  const usageTotals = useMemo(() => {
    const t: Record<string, { req: number; inTok: number; outTok: number; cost: number }> = {};
    for (const u of usage.data ?? []) {
      const k = `${u.provider} · ${u.model}`;
      t[k] ??= { req: 0, inTok: 0, outTok: 0, cost: 0 };
      t[k].req++; t[k].inTok += u.input_tokens; t[k].outTok += u.output_tokens; t[k].cost += Number(u.est_cost_usd);
    }
    return Object.entries(t);
  }, [usage.data]);

  return (
    <>
      <PageHeader title="Settings & Source Health" subtitle="Enable sources, adjust intervals, and see exactly what failed and when. Credentials are never shown here — they live in GitHub Actions secrets." />
      {msg && <p role="status" className="mb-4 rounded-md border border-line bg-panel2 p-2 text-sm">{msg}</p>}

      <Section title="Pipeline">
        {status.error ? <ErrorBox error={status.error} /> : status.data ? (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <div className="stat"><div className="stat-n text-base">{timeAgo(status.data.last_collect_success)}</div><div className="stat-l" title={formatIST(status.data.last_collect_success)}>Last successful collection</div></div>
            <div className="stat"><div className="stat-n text-base">{timeAgo(status.data.last_process_success)}</div><div className="stat-l">Last successful processing</div></div>
            <div className="stat"><div className="stat-n text-base">${Number(status.data.cost_today_usd).toFixed(3)}</div><div className="stat-l">Est. model cost today</div></div>
            <div className="stat"><div className="stat-n text-base">${Number(status.data.cost_month_usd).toFixed(2)}</div><div className="stat-l">Est. model cost this month</div></div>
          </div>
        ) : <Skeleton rows={1} />}
      </Section>

      <Section title="Sources">
        {sources.error ? <ErrorBox error={sources.error} onRetry={sources.reload} /> : !sources.data ? <Skeleton /> : (
          <div className="card overflow-x-auto p-0">
            <table className="table min-w-[760px]">
              <thead><tr><th>Source</th><th>Health</th><th>Last success</th><th>Newest item</th><th>Interval</th><th>Enabled</th></tr></thead>
              <tbody>
                {sources.data.map((s) => {
                  const h = s.source_health;
                  return (
                    <tr key={s.id}>
                      <td>
                        <div className="font-medium">{s.homepage ? <ExtLink href={s.homepage}>{s.name}</ExtLink> : s.name}</div>
                        <div className="text-xs text-muted">{s.adapter}{s.is_official ? " · official" : ""} · reliability {s.reliability}/5</div>
                        {h?.last_error && <div className="mt-1 max-w-md break-words font-mono text-[11px] text-red-300">{h.last_error}</div>}
                        {s.notes && <div className="mt-1 text-xs text-muted">{s.notes}</div>}
                      </td>
                      <td><Badge cls={HEALTH_CLS[h?.status ?? "unknown"]}>{s.enabled ? (h?.status ?? "unknown") : "disabled"}</Badge>
                        {h && h.consecutive_failures > 0 && <div className="mt-1 text-xs text-muted">{h.consecutive_failures} failures in a row</div>}</td>
                      <td className="text-xs" title={formatIST(h?.last_success_at)}>{timeAgo(h?.last_success_at)}</td>
                      <td className="text-xs" title={formatIST(h?.last_item_published_at)}>{h?.last_item_published_at ? timeAgo(h.last_item_published_at) : "–"}</td>
                      <td className="text-xs">{s.interval_minutes < 60 ? `every ${s.interval_minutes} min` : `every ${s.interval_minutes / 60} h`}</td>
                      <td>
                        <input type="checkbox" className="h-4 w-4 accent-[var(--color-accent)]" checked={s.enabled} aria-label={`Enable ${s.name}`}
                          onChange={(e) => act(() => setSourceEnabled(s.id, e.target.checked), `${s.name} ${e.target.checked ? "enabled" : "disabled"}`, sources.reload)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-2 text-xs text-muted">The collector wakes every 5 minutes on GitHub Actions and fetches each source when its interval (set in config/sources.json) is due. GitHub can delay scheduled runs, so a source is only marked delayed when it is well past its interval.</p>
      </Section>

      <div className="grid gap-8 lg:grid-cols-2">
        <Section title="Categories">
          {cats.error ? <ErrorBox error={cats.error} /> : !cats.data ? <Skeleton rows={1} /> : (
            <ul className="card space-y-1.5 text-sm">
              {cats.data.map((c) => (
                <li key={c.slug} className="flex items-center justify-between gap-2">
                  <span>{c.name} <span className="text-xs text-muted">priority {c.priority}</span></span>
                  <input type="checkbox" className="h-4 w-4 accent-[var(--color-accent)]" checked={c.enabled} aria-label={`Enable ${c.name}`}
                    onChange={(e) => act(() => setCategoryEnabled(c.slug, e.target.checked), `${c.name} updated`, cats.reload)} />
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Processing & budget">
          <div className="card space-y-3 text-sm">
            {settings.data && (["daily_budget_usd", "summarize_min_score", "max_items_per_process_run"] as const).map((k) => (
              <form key={k} className="flex items-center justify-between gap-2" onSubmit={(e) => {
                e.preventDefault();
                const v = Number(new FormData(e.currentTarget).get("v"));
                act(() => setSetting(k, v), `${k} saved`, settings.reload);
              }}>
                <label htmlFor={k} className="text-muted">{({ daily_budget_usd: "Daily model budget (USD)", summarize_min_score: "Min score for AI summary", max_items_per_process_run: "Max items per processing run" })[k]}</label>
                <span className="flex gap-1"><input id={k} name="v" type="number" step="any" min={0} max={1000} className="input w-24 py-1"
                  defaultValue={String(settings.data?.[k] ?? "")} disabled={auth.status === "ready" && auth.demo} /><button className="btn py-1">Save</button></span>
              </form>
            ))}
            <p className="text-xs text-muted">The pipeline also enforces the DAILY_BUDGET_USD cap from its secrets; the lower of the two wins. Cost is an estimate from the per-token prices you configure.</p>
          </div>
        </Section>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <Section title="Provider configuration">
          {!providerStatus ? <Empty>No run has reported its configuration yet.</Empty> : (
            <ul className="card space-y-1 text-sm">
              {Object.entries(providerStatus).map(([k, v]) => (
                <li key={k} className="flex justify-between gap-2"><span className="text-muted">{k.replace(/_/g, " ")}</span>
                  <span className="font-mono text-xs">{typeof v === "boolean" ? (v ? "✓ configured" : "✗ not set") : (String(v) || "–")}</span></li>
              ))}
            </ul>
          )}
        </Section>
        <Section title="Model usage · 7 days">
          {!usageTotals.length ? <Empty>No model calls recorded.</Empty> : (
            <div className="card overflow-x-auto p-0"><table className="table"><thead><tr><th>Provider · model</th><th>Calls</th><th>Tokens in/out</th><th>Est. cost</th></tr></thead>
              <tbody>{usageTotals.map(([k, t]) => <tr key={k}><td className="text-xs">{k}</td><td>{t.req}</td><td className="text-xs">{t.inTok.toLocaleString()} / {t.outTok.toLocaleString()}</td><td>${t.cost.toFixed(4)}</td></tr>)}</tbody></table></div>
          )}
        </Section>
      </div>

      <Section title="Recent workflow runs">
        {runs.error ? <ErrorBox error={runs.error} /> : !runs.data?.length ? <Empty>No runs recorded yet. Trigger the “Collect sources” workflow manually in GitHub Actions.</Empty> : (
          <div className="card overflow-x-auto p-0"><table className="table min-w-[640px]"><thead><tr><th>Workflow</th><th>Status</th><th>Started</th><th>Result</th><th>Log</th></tr></thead>
            <tbody>{runs.data.map((r) => (
              <tr key={r.id}>
                <td>{r.workflow}</td>
                <td><Badge cls={r.status === "success" ? "badge-green" : r.status === "partial" ? "badge-amber" : r.status === "running" ? "badge-sky" : "badge-red"}>{r.status}</Badge></td>
                <td className="text-xs" title={formatIST(r.started_at)}>{timeAgo(r.started_at)}</td>
                <td className="text-xs text-muted">{r.error ?? summarize(r.stats)}</td>
                <td className="text-xs">{r.github_run_url ? <ExtLink href={r.github_run_url}>Actions ↗</ExtLink> : "–"}</td>
              </tr>))}</tbody></table></div>
        )}
      </Section>

      <Section title="Failed or partial collections">
        {!failed.data?.length ? <Empty>No failed collection jobs recorded.</Empty> : (
          <div className="card overflow-x-auto p-0"><table className="table min-w-[640px]"><thead><tr><th>Source</th><th>When</th><th>Status</th><th>Error</th></tr></thead>
            <tbody>{failed.data.map((f) => (
              <tr key={f.id}><td>{f.source_id}</td><td className="text-xs" title={formatIST(f.started_at)}>{timeAgo(f.started_at)}</td>
                <td><Badge cls={f.status === "failed" ? "badge-red" : "badge-amber"}>{f.status}</Badge></td>
                <td className="break-words font-mono text-[11px] text-muted">{f.error}</td></tr>))}</tbody></table></div>
        )}
      </Section>
    </>
  );
}

function summarize(stats: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const k of ["items_new", "items_duplicate", "processed", "llm", "items"]) if (k in stats) parts.push(`${k.replace("items_", "")}: ${stats[k]}`);
  return parts.join(" · ");
}
