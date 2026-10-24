import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

/** Demo mode = no Supabase configured at build time. The UI then shows clearly labelled sample data. */
export const IS_DEMO = !url || !key;
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

let client: SupabaseClient | null = null;

export function supabase(): SupabaseClient {
  if (IS_DEMO) throw new Error("Supabase is not configured (demo mode)");
  if (!client) {
    client = createClient(url, key, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: "pkce" },
    });
  }
  return client;
}
