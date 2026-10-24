#!/usr/bin/env node
// Fails if anything that looks like a privileged credential appears in the given paths
// (the built site in CI, or the repository's tracked files). Publishable/anon keys are allowed.
// Usage: node scripts/check-secrets.mjs <dir-or-file> [...]   |   node scripts/check-secrets.mjs --git
import { execSync } from "node:child_process";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const PATTERNS = [
  ["Supabase secret key", /sb_secret_[A-Za-z0-9_-]{10,}/],
  ["GitHub token", /\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b/],
  ["OpenAI-style key", /\bsk-(proj-|ant-)?[A-Za-z0-9_-]{30,}\b/],
  ["Private key block", /-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----/],
  ["Brave/Exa key assignment", /(SEARCH_API_KEY|LLM_API_KEY|SUPABASE_SERVICE_ROLE_KEY)[ \t]*=[ \t]*["']?(?!REPLACE|your|<|\$\{|\s|$)[A-Za-z0-9_\-]{16,}/],
];
const JWT = /eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g;
const SKIP = /(^|\/)(node_modules|\.git|\.venv|\.next|__pycache__)(\/|$)|\.(png|jpg|jpeg|gif|ico|woff2?|ttf|webp|lock)$/;

// Values of real secrets present in the CI environment must never appear in output.
const envSecrets = ["SUPABASE_SERVICE_ROLE_KEY", "LLM_API_KEY", "SEARCH_API_KEY", "REDDIT_CLIENT_SECRET", "GH_API_TOKEN"]
  .map((k) => process.env[k]).filter((v) => v && v.length >= 12);

function* walk(p) {
  if (SKIP.test(p)) return;
  const st = statSync(p);
  if (st.isDirectory()) for (const f of readdirSync(p)) yield* walk(join(p, f));
  else if (st.size < 8_000_000) yield p;
}

const files = process.argv[2] === "--git"
  ? execSync("git ls-files", { encoding: "utf8" }).split("\n").filter((f) => f && !SKIP.test(f))
  : process.argv.slice(2).flatMap((p) => [...walk(p)]);

let problems = 0;
for (const f of files) {
  if (f.endsWith("check-secrets.mjs")) continue;
  let text;
  try { text = readFileSync(f, "utf8"); } catch { continue; }
  for (const [name, re] of PATTERNS) if (re.test(text)) { console.error(`✗ ${name} in ${f}`); problems++; }
  for (const m of text.matchAll(JWT)) {
    try {
      const payload = JSON.parse(Buffer.from(m[0].split(".")[1], "base64url").toString());
      if (payload.role === "service_role") { console.error(`✗ Supabase service_role JWT in ${f}`); problems++; }
    } catch { /* not a JWT */ }
  }
  for (const s of envSecrets) if (text.includes(s)) { console.error(`✗ value of a secret environment variable found in ${f}`); problems++; }
  if (/(^|\/)\.env(\.local|\.production)?$/.test(f)) { console.error(`✗ committed env file ${f}`); problems++; }
}
if (problems) { console.error(`\n${problems} potential secret(s) found.`); process.exit(1); }
console.log(`✓ no secrets found in ${files.length} files`);
