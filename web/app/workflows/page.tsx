"use client";
import { Badge, Empty, ErrorBox, ExtLink, PageHeader, Skeleton } from "@/components/ui";
import { getPracticalWorkflows } from "@/lib/api";
import { useAsync } from "@/lib/hooks";

export default function Workflows() {
  const { data, error, loading, reload } = useAsync(getPracticalWorkflows, []);
  return (
    <>
      <PageHeader title="Practical Workflows" subtitle="Reproducible recipes that combine tools to do real work. Costs are approximate; a workflow is marked Verified only after you've run it yourself." />
      {error ? <ErrorBox error={error} onRetry={reload} /> : loading ? <Skeleton /> : !data?.length ? (
        <Empty>No workflows yet. Add them to the <code>workflows</code> table (see docs/OPERATIONS.md).</Empty>
      ) : (
        <div className="space-y-4">
          {data.map((w) => (
            <article key={w.id} className="card">
              <div className="mb-2 flex flex-wrap gap-1.5">
                <Badge cls={w.verified ? "badge-green" : "badge-muted"}>{w.verified ? "Verified by you" : "Not yet tested"}</Badge>
                {w.approx_cost && <Badge cls="badge-outline">Cost: {w.approx_cost}</Badge>}
              </div>
              <h2 className="text-lg font-semibold text-ink">{w.title}</h2>
              <p className="mt-1 text-sm text-ink/80"><strong>Objective:</strong> {w.objective}</p>
              <div className="mt-3 grid gap-4 text-sm md:grid-cols-2">
                <div>
                  <h3 className="section-title mb-1">Tools required</h3>
                  <ul className="list-disc pl-5 text-ink/80">{w.tools_required.map((t) => <li key={t}>{t}</li>)}</ul>
                  {w.setup && <><h3 className="section-title mb-1 mt-3">Setup</h3><p className="text-ink/80">{w.setup}</p></>}
                  {w.expected_result && <><h3 className="section-title mb-1 mt-3">Expected result</h3><p className="text-ink/80">{w.expected_result}</p></>}
                </div>
                <div>
                  <h3 className="section-title mb-1">Steps</h3>
                  <ol className="list-decimal space-y-1 pl-5 text-ink/80">{(w.steps ?? []).map((s, i) => <li key={i}>{s}</li>)}</ol>
                </div>
              </div>
              <div className="mt-4 grid gap-3 text-sm md:grid-cols-2">
                {w.limitations && <p className="rounded-md bg-panel2 p-3"><strong className="text-amber-300">Limitations:</strong> {w.limitations}</p>}
                {w.security_notes && <p className="rounded-md bg-panel2 p-3"><strong className="text-red-300">Security:</strong> {w.security_notes}</p>}
              </div>
              {w.doc_links.length > 0 && (
                <p className="mt-3 text-xs">Official docs: {w.doc_links.map((u) => <ExtLink key={u} href={u} className="mr-3">{u} ↗</ExtLink>)}</p>
              )}
            </article>
          ))}
        </div>
      )}
    </>
  );
}
