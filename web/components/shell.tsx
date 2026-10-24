"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { getPipelineStatus } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { IS_DEMO } from "@/lib/supabase";
import { AuthProvider, sendMagicLink, signOut, useAuth } from "./auth";
import { FreshnessPill } from "./ui";

const NAV = [
  ["/", "Overview"], ["/news/", "AI News"], ["/tools/", "Tools Directory"], ["/gems/", "Hidden Gems"],
  ["/github/", "GitHub & Open Source"], ["/agents/", "Agents & Automation"], ["/research/", "Research & Models"],
  ["/workflows/", "Practical Workflows"], ["/search/", "Search & Archive"], ["/bookmarks/", "Bookmarks"],
  ["/settings/", "Settings & Health"],
] as const;

function RadarMark() {
  return (
    <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden="true">
      <circle cx="16" cy="16" r="14" fill="none" stroke="currentColor" strokeOpacity=".35" />
      <circle cx="16" cy="16" r="8.5" fill="none" stroke="currentColor" strokeOpacity=".35" />
      <path d="M16 16 L16 2 A14 14 0 0 1 28.1 9 Z" fill="currentColor" fillOpacity=".35" className="origin-center animate-[spin_6s_linear_infinite]" />
      <circle cx="21" cy="11" r="1.6" fill="currentColor" />
    </svg>
  );
}

function Login() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [err, setErr] = useState<string | null>(null);
  return (
    <main className="grid min-h-screen place-items-center p-4">
      <form className="card w-full max-w-sm" onSubmit={async (e) => {
        e.preventDefault(); setErr(null); setState("sending");
        try { await sendMagicLink(email); setState("sent"); } catch (x) { setErr(x instanceof Error ? x.message : "Failed"); setState("idle"); }
      }}>
        <div className="mb-4 flex items-center gap-2 text-accent"><RadarMark /><span className="font-semibold tracking-wide text-ink">AI RADAR</span></div>
        <h1 className="text-lg font-semibold text-ink">Private dashboard</h1>
        <p className="mt-1 text-sm text-muted">Sign in with the email on the owner allowlist. We&apos;ll send a one-time link.</p>
        {state === "sent" ? (
          <p className="mt-4 rounded-md bg-accent/10 p-3 text-sm text-accent">Check your inbox for the sign-in link. It works in this browser only.</p>
        ) : (
          <>
            <label htmlFor="email" className="mt-4 block text-xs font-medium text-muted">Email</label>
            <input id="email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)}
              className="input mt-1 w-full" placeholder="you@example.com" maxLength={254} />
            <button className="btn btn-primary mt-4 w-full" disabled={state === "sending"}>{state === "sending" ? "Sending…" : "Email me a sign-in link"}</button>
          </>
        )}
        {err && <p role="alert" className="mt-3 text-sm text-red-300">{err}</p>}
      </form>
    </main>
  );
}

function Gate({ children }: { children: ReactNode }) {
  const auth = useAuth();
  if (auth.status === "loading") return <div className="grid min-h-screen place-items-center text-muted">Checking session…</div>;
  if (auth.status === "signed_out") return <Login />;
  if (auth.status === "unauthorised") return (
    <main className="grid min-h-screen place-items-center p-4">
      <div className="card max-w-md text-sm">
        <h1 className="text-lg font-semibold text-ink">Not authorised</h1>
        <p className="mt-2 text-muted">{auth.email} is signed in but isn&apos;t on this dashboard&apos;s allowlist, so the database returns no data.</p>
        <button className="btn mt-4" onClick={() => signOut()}>Sign out</button>
      </div>
    </main>
  );
  return <Frame>{children}</Frame>;
}

function StatusStrip() {
  const { data } = useAsync(getPipelineStatus, []);
  if (!data) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <FreshnessPill iso={data.last_collect_success} expectedMinutes={45} label="Collected" />
      {data.failing_sources > 0 && <Link href="/settings/" className="badge badge-red">{data.failing_sources} source{data.failing_sources > 1 ? "s" : ""} failing</Link>}
      {data.delayed_sources > 0 && <Link href="/settings/" className="badge badge-amber">{data.delayed_sources} delayed</Link>}
    </div>
  );
}

function Frame({ children }: { children: ReactNode }) {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const auth = useAuth();
  const nav = (
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {NAV.map(([href, label]) => {
        const active = href === "/" ? path === "/" : path?.startsWith(href.replace(/\/$/, ""));
        return <Link key={href} href={href} onClick={() => setOpen(false)} aria-current={active ? "page" : undefined}
          className={`navlink ${active ? "navlink-on" : ""}`}>{label}</Link>;
      })}
    </nav>
  );
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-line bg-bg/80 p-4 lg:flex">
        <Link href="/" className="mb-6 flex items-center gap-2 text-accent"><RadarMark /><span className="font-semibold tracking-[.18em] text-ink">AI RADAR</span></Link>
        {nav}
        <div className="mt-auto space-y-2 border-t border-line pt-3 text-xs text-muted">
          <p className="truncate" title={auth.status === "ready" ? auth.email : ""}>{auth.status === "ready" && !auth.demo ? auth.email : "Demo mode"}</p>
          {!IS_DEMO && <button className="link" onClick={() => signOut()}>Sign out</button>}
        </div>
      </aside>
      <div className="min-w-0">
        <div className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-line bg-bg/90 px-4 py-2.5 backdrop-blur">
          <button className="btn lg:hidden" aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen(!open)}>☰ Menu</button>
          <Link href="/" className="flex items-center gap-2 text-accent lg:hidden"><RadarMark /></Link>
          <div className="ml-auto"><StatusStrip /></div>
        </div>
        {open && <div id="mobile-nav" className="border-b border-line bg-bg p-3 lg:hidden">{nav}</div>}
        {IS_DEMO && (
          <div className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-200">
            <strong>Demo mode — sample data only.</strong> This build has no Supabase connection, so everything shown is labelled [SAMPLE] and is not real news.
          </div>
        )}
        <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  return <AuthProvider><Gate>{children}</Gate></AuthProvider>;
}
