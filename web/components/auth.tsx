"use client";
import type { Session } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { BASE_PATH, IS_DEMO, supabase } from "@/lib/supabase";

type AuthState =
  | { status: "loading" }
  | { status: "signed_out" }
  | { status: "unauthorised"; email: string }
  | { status: "ready"; session: Session | null; email: string; demo: boolean };

const Ctx = createContext<AuthState>({ status: "loading" });
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(IS_DEMO
    ? { status: "ready", session: null, email: "demo", demo: true } : { status: "loading" });

  useEffect(() => {
    if (IS_DEMO) return;
    const sb = supabase();
    const check = async (session: Session | null) => {
      if (!session) return setState({ status: "signed_out" });
      const email = session.user.email ?? "";
      // RLS lets a user read only their own allowlist row: no row = not authorised.
      const { data, error } = await sb.from("allowed_users").select("email").maybeSingle();
      if (error || !data) return setState({ status: "unauthorised", email });
      setState({ status: "ready", session, email, demo: false });
    };
    sb.auth.getSession().then(({ data }) => check(data.session));
    const { data: sub } = sb.auth.onAuthStateChange((_e, session) => { void check(session); });
    return () => sub.subscription.unsubscribe();
  }, []);

  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}

export async function sendMagicLink(email: string): Promise<void> {
  const clean = email.trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(clean)) throw new Error("Enter a valid email address");
  const { error } = await supabase().auth.signInWithOtp({
    email: clean,
    // Never create accounts from the login form; the owner account is created in the Supabase dashboard.
    options: { shouldCreateUser: false, emailRedirectTo: `${window.location.origin}${BASE_PATH}/` },
  });
  if (error) throw new Error(error.message);
}

export async function signOut(): Promise<void> {
  if (!IS_DEMO) await supabase().auth.signOut();
}
