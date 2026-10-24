-- AI RADAR: complete database setup. Paste ALL of this into Supabase → SQL Editor → New query → Run.
-- Safe to run once on a NEW project.

-- ===== supabase/migrations/20261024000001_schema.sql =====
-- AI RADAR core schema. All timestamps are timestamptz stored in UTC.
create extension if not exists pg_trgm;
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Access control: only emails on this allowlist can read any data.
-- Sign-ups should also be disabled in Supabase Auth settings.
-- ---------------------------------------------------------------------------
create table public.allowed_users (
  email text primary key check (email = lower(email)),
  role text not null default 'owner' check (role in ('owner', 'viewer')),
  created_at timestamptz not null default now()
);

create or replace function public.is_member() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.allowed_users
    where email = lower(coalesce(auth.jwt() ->> 'email', ''))
  );
$$;

create or replace function public.is_owner() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.allowed_users
    where email = lower(coalesce(auth.jwt() ->> 'email', '')) and role = 'owner'
  );
$$;

revoke all on function public.is_member() from public;
revoke all on function public.is_owner() from public;
grant execute on function public.is_member() to authenticated;
grant execute on function public.is_owner() to authenticated;

-- ---------------------------------------------------------------------------
-- Reference data
-- ---------------------------------------------------------------------------
create table public.categories (
  slug text primary key,
  name text not null,
  description text,
  priority smallint not null default 5,  -- 1 = highest personal priority
  enabled boolean not null default true,
  keywords text[] not null default '{}'
);

create table public.tags (
  id bigint generated always as identity primary key,
  slug text not null unique,
  name text not null
);

create table public.sources (
  id text primary key,                         -- stable slug, e.g. "hn-ai"
  name text not null,
  adapter text not null,                       -- rss | github_releases | hackernews | reddit | huggingface | arxiv | web_search
  config jsonb not null default '{}',          -- adapter-specific settings (no secrets!)
  reliability smallint not null default 3 check (reliability between 1 and 5),
  is_official boolean not null default false,
  enabled boolean not null default true,
  interval_minutes integer not null default 60 check (interval_minutes >= 15),
  default_category text references public.categories(slug),
  homepage text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Discoveries
-- ---------------------------------------------------------------------------
create type public.discovery_type as enum
  ('news', 'tool', 'repo', 'model', 'paper', 'agent', 'workflow', 'discussion', 'dataset', 'other');
create type public.verification_status as enum
  ('unverified', 'source_reported', 'official', 'multi_source', 'disputed');
create type public.importance_label as enum
  ('must_know', 'worth_trying', 'experimental', 'watchlist', 'low');
create type public.pricing_category as enum
  ('free', 'freemium', 'paid', 'open_source', 'enterprise', 'unknown');

create table public.discoveries (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  normalized_title text not null,
  canonical_url text not null,
  url_hash text not null unique,             -- sha256 of canonical_url
  content_hash text,                         -- sha256 of normalized body text
  discovery_type public.discovery_type not null default 'news',
  primary_category text references public.categories(slug),

  -- Distinct timestamps; NULL means "not known", never guessed.
  published_at timestamptz,
  released_at timestamptz,
  updated_at_source timestamptz,
  first_discovered_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  last_verified_at timestamptz,

  raw_excerpt text,                          -- untrusted source text, rendered as plain text only
  summary_short text,
  summary_detailed text,
  why_it_matters text,
  practical_usefulness text,
  known_limitations text,
  claims_note text,                          -- marketing vs demonstrated, vendor vs independent benchmarks

  verification_status public.verification_status not null default 'unverified',
  importance public.importance_label not null default 'watchlist',
  score numeric(6,2) not null default 0,
  score_breakdown jsonb not null default '{}',

  -- Tool / repo metadata (nullable where not applicable)
  pricing public.pricing_category not null default 'unknown',
  pricing_evidence_url text,
  free_tier_notes text,
  is_open_source boolean,
  license text,
  stars integer,
  setup_requirements text,
  hardware_requirements text,
  security_notes text,
  maintenance_signals jsonb,
  is_hidden_gem boolean not null default false,

  -- Processing state
  processing_status text not null default 'pending' check (processing_status in ('pending','processed','failed','skipped')),
  processing_error text,
  processed_at timestamptz,
  model_used text,
  duplicate_of uuid references public.discoveries(id) on delete set null,
  dedupe_meta jsonb not null default '{}',
  extra jsonb not null default '{}',

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index discoveries_first_discovered_idx on public.discoveries (first_discovered_at desc);
create index discoveries_published_idx on public.discoveries (published_at desc nulls last);
create index discoveries_type_idx on public.discoveries (discovery_type);
create index discoveries_category_idx on public.discoveries (primary_category);
create index discoveries_importance_idx on public.discoveries (importance, score desc);
create index discoveries_processing_idx on public.discoveries (processing_status) where processing_status = 'pending';
create index discoveries_content_hash_idx on public.discoveries (content_hash);
create index discoveries_title_trgm_idx on public.discoveries using gin (normalized_title gin_trgm_ops);

alter table public.discoveries add column search_vector tsvector
  generated always as (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(summary_short, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(summary_detailed, '') || ' ' || coalesce(why_it_matters, '')), 'C')
  ) stored;
create index discoveries_search_idx on public.discoveries using gin (search_vector);

-- Every source sighting of a discovery (one discovery can be reported by many sources).
create table public.discovery_sources (
  discovery_id uuid not null references public.discoveries(id) on delete cascade,
  source_id text not null references public.sources(id) on delete cascade,
  source_url text not null,
  external_id text,
  raw_meta jsonb not null default '{}',
  seen_at timestamptz not null default now(),
  primary key (discovery_id, source_id, source_url)
);
create index discovery_sources_source_idx on public.discovery_sources (source_id, seen_at desc);

create table public.discovery_categories (
  discovery_id uuid not null references public.discoveries(id) on delete cascade,
  category_slug text not null references public.categories(slug) on delete cascade,
  primary key (discovery_id, category_slug)
);

create table public.discovery_tags (
  discovery_id uuid not null references public.discoveries(id) on delete cascade,
  tag_id bigint not null references public.tags(id) on delete cascade,
  primary key (discovery_id, tag_id)
);

-- Evidence links used for verification (official docs, pricing pages, etc.)
create table public.evidence_links (
  id bigint generated always as identity primary key,
  discovery_id uuid not null references public.discoveries(id) on delete cascade,
  url text not null,
  kind text not null default 'reference' check (kind in ('official','pricing','docs','repo','independent','reference')),
  checked_at timestamptz,
  http_status integer,
  unique (discovery_id, url)
);

-- Curated practical workflows
create table public.workflows (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  title text not null,
  objective text not null,
  tools_required text[] not null default '{}',
  setup text,
  steps jsonb not null default '[]',
  approx_cost text,
  expected_result text,
  limitations text,
  security_notes text,
  doc_links text[] not null default '{}',
  category text references public.categories(slug),
  verified boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Daily briefings
create table public.briefings (
  id uuid primary key default gen_random_uuid(),
  briefing_date date not null unique,
  title text not null,
  body_markdown text not null,
  discovery_ids uuid[] not null default '{}',
  model_used text,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Private user data
-- ---------------------------------------------------------------------------
create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  timezone text not null default 'Asia/Kolkata',
  preferred_categories text[] not null default '{}',
  muted_sources text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.bookmarks (
  user_id uuid not null references auth.users(id) on delete cascade default auth.uid(),
  discovery_id uuid not null references public.discoveries(id) on delete cascade,
  status text not null default 'saved' check (status in ('saved','tried','not_useful')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, discovery_id)
);

create table public.user_notes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade default auth.uid(),
  discovery_id uuid not null references public.discoveries(id) on delete cascade,
  body text not null check (char_length(body) between 1 and 5000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index user_notes_user_idx on public.user_notes (user_id, discovery_id);

-- ---------------------------------------------------------------------------
-- Operations / observability
-- ---------------------------------------------------------------------------
create table public.ingestion_runs (
  id uuid primary key default gen_random_uuid(),
  source_id text not null references public.sources(id) on delete cascade,
  workflow_run_id uuid,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running' check (status in ('running','success','partial','failed','skipped')),
  items_fetched integer not null default 0,
  items_new integer not null default 0,
  items_duplicate integer not null default 0,
  error text
);
create index ingestion_runs_source_idx on public.ingestion_runs (source_id, started_at desc);

create table public.workflow_runs (
  id uuid primary key default gen_random_uuid(),
  workflow text not null,                       -- collect | process | briefing
  github_run_id text,
  github_run_url text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running' check (status in ('running','success','partial','failed')),
  stats jsonb not null default '{}',
  error text
);
create index workflow_runs_started_idx on public.workflow_runs (workflow, started_at desc);

create table public.source_health (
  source_id text primary key references public.sources(id) on delete cascade,
  last_attempt_at timestamptz,
  last_success_at timestamptz,
  last_item_published_at timestamptz,
  consecutive_failures integer not null default 0,
  last_error text,
  status text not null default 'unknown' check (status in ('unknown','healthy','delayed','failing','disabled')),
  updated_at timestamptz not null default now()
);

create table public.api_usage (
  id bigint generated always as identity primary key,
  provider text not null,
  model text,
  purpose text not null,
  input_tokens integer not null default 0,
  output_tokens integer not null default 0,
  requests integer not null default 1,
  est_cost_usd numeric(10,5) not null default 0,
  created_at timestamptz not null default now()
);
create index api_usage_created_idx on public.api_usage (created_at desc);

-- Non-secret runtime settings editable from the dashboard
create table public.app_settings (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

-- updated_at triggers
create or replace function public.touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end; $$;

create trigger t_sources_touch before update on public.sources for each row execute function public.touch_updated_at();
create trigger t_discoveries_touch before update on public.discoveries for each row execute function public.touch_updated_at();
create trigger t_bookmarks_touch before update on public.bookmarks for each row execute function public.touch_updated_at();
create trigger t_notes_touch before update on public.user_notes for each row execute function public.touch_updated_at();
create trigger t_profiles_touch before update on public.profiles for each row execute function public.touch_updated_at();
create trigger t_workflows_touch before update on public.workflows for each row execute function public.touch_updated_at();

-- ===== supabase/migrations/20261024000002_rls.sql =====
-- Row Level Security. Default deny everywhere; the pipeline uses the
-- service-role key (bypasses RLS) from GitHub Actions only.

alter table public.allowed_users      enable row level security;
alter table public.categories         enable row level security;
alter table public.tags               enable row level security;
alter table public.sources            enable row level security;
alter table public.discoveries        enable row level security;
alter table public.discovery_sources  enable row level security;
alter table public.discovery_categories enable row level security;
alter table public.discovery_tags     enable row level security;
alter table public.evidence_links     enable row level security;
alter table public.workflows          enable row level security;
alter table public.briefings          enable row level security;
alter table public.profiles           enable row level security;
alter table public.bookmarks          enable row level security;
alter table public.user_notes         enable row level security;
alter table public.ingestion_runs     enable row level security;
alter table public.workflow_runs      enable row level security;
alter table public.source_health      enable row level security;
alter table public.api_usage          enable row level security;
alter table public.app_settings       enable row level security;

-- Anonymous visitors get nothing. Remove default grants to anon entirely.
revoke all on all tables in schema public from anon;
revoke all on all sequences in schema public from anon;
revoke all on all functions in schema public from anon;
alter default privileges in schema public revoke all on tables from anon;
alter default privileges in schema public revoke all on functions from anon;

-- Allowlist: a member may see only their own row (used by the UI to show "not authorised").
create policy allowed_users_self on public.allowed_users
  for select to authenticated using (email = lower(coalesce(auth.jwt() ->> 'email', '')));

-- Shared intelligence content: readable by members only.
do $$
declare t text;
begin
  foreach t in array array['categories','tags','sources','discoveries','discovery_sources',
    'discovery_categories','discovery_tags','evidence_links','workflows','briefings',
    'ingestion_runs','workflow_runs','source_health','api_usage','app_settings']
  loop
    execute format('create policy %I on public.%I for select to authenticated using (public.is_member())',
                   t || '_member_read', t);
  end loop;
end $$;

-- Owners may toggle sources/categories and edit non-secret settings from the dashboard.
create policy sources_owner_update on public.sources
  for update to authenticated using (public.is_owner()) with check (public.is_owner());
create policy categories_owner_update on public.categories
  for update to authenticated using (public.is_owner()) with check (public.is_owner());
create policy app_settings_owner_write on public.app_settings
  for all to authenticated using (public.is_owner()) with check (public.is_owner());


-- Private per-user data: strictly the owner's own rows.
create policy profiles_own on public.profiles
  for all to authenticated
  using (user_id = auth.uid() and public.is_member())
  with check (user_id = auth.uid() and public.is_member());

create policy bookmarks_own on public.bookmarks
  for all to authenticated
  using (user_id = auth.uid() and public.is_member())
  with check (user_id = auth.uid() and public.is_member());

create policy notes_own on public.user_notes
  for all to authenticated
  using (user_id = auth.uid() and public.is_member())
  with check (user_id = auth.uid() and public.is_member());

-- Table privileges for signed-in users: read-only by default (RLS still filters every row).
-- Supabase grants ALL to `authenticated` out of the box; tighten that so shared content is
-- writable only by the pipeline's service role.
revoke all on all tables in schema public from authenticated;
alter default privileges in schema public revoke insert, update, delete, truncate on tables from authenticated;
grant select on all tables in schema public to authenticated;
grant insert, update, delete on public.bookmarks, public.user_notes, public.profiles to authenticated;
grant insert, update, delete on public.app_settings to authenticated;
-- Column-level restriction: owners may only change these columns from the dashboard.
grant update (enabled, interval_minutes, notes) on public.sources to authenticated;
grant update (enabled, priority) on public.categories to authenticated;

-- ===== supabase/migrations/20261024000003_functions.sql =====
-- Query helpers for the dashboard. All are SECURITY INVOKER so RLS applies.

create or replace function public.search_discoveries(
  q text default null,
  p_types public.discovery_type[] default null,
  p_category text default null,
  p_source text default null,
  p_pricing public.pricing_category default null,
  p_open_source boolean default null,
  p_verification public.verification_status default null,
  p_importance public.importance_label default null,
  p_bookmark_status text default null,       -- saved | tried | not_useful | any
  p_hidden_gems boolean default null,
  p_published_from timestamptz default null,
  p_published_to timestamptz default null,
  p_discovered_from timestamptz default null,
  p_discovered_to timestamptz default null,
  p_sort text default 'discovered',          -- discovered | published | score | relevance
  p_limit integer default 25,
  p_offset integer default 0
) returns table (
  id uuid, title text, canonical_url text, discovery_type public.discovery_type,
  primary_category text, published_at timestamptz, first_discovered_at timestamptz,
  last_verified_at timestamptz, summary_short text, why_it_matters text,
  verification_status public.verification_status, importance public.importance_label,
  score numeric, pricing public.pricing_category, is_open_source boolean, license text,
  stars integer, is_hidden_gem boolean, source_names text[], tags text[],
  bookmark_status text, total_count bigint
)
language sql stable security invoker set search_path = public as $$
  with base as (
    select d.*,
      case when q is null or q = '' then 0
           else ts_rank(d.search_vector, websearch_to_tsquery('english', q)) end as rank
    from discoveries d
    left join bookmarks b on b.discovery_id = d.id and b.user_id = auth.uid()
    where d.duplicate_of is null
      and (q is null or q = '' or d.search_vector @@ websearch_to_tsquery('english', q)
           or d.normalized_title % lower(q))
      and (p_types is null or d.discovery_type = any(p_types))
      and (p_category is null or d.primary_category = p_category
           or exists (select 1 from discovery_categories dc where dc.discovery_id = d.id and dc.category_slug = p_category))
      and (p_source is null or exists (select 1 from discovery_sources ds where ds.discovery_id = d.id and ds.source_id = p_source))
      and (p_pricing is null or d.pricing = p_pricing)
      and (p_open_source is null or d.is_open_source = p_open_source)
      and (p_verification is null or d.verification_status = p_verification)
      and (p_importance is null or d.importance = p_importance)
      and (p_hidden_gems is null or d.is_hidden_gem = p_hidden_gems)
      and (p_bookmark_status is null
           or (p_bookmark_status = 'any' and b.status is not null)
           or b.status = p_bookmark_status)
      and (p_published_from is null or d.published_at >= p_published_from)
      and (p_published_to is null or d.published_at < p_published_to)
      and (p_discovered_from is null or d.first_discovered_at >= p_discovered_from)
      and (p_discovered_to is null or d.first_discovered_at < p_discovered_to)
  )
  select b.id, b.title, b.canonical_url, b.discovery_type, b.primary_category, b.published_at,
    b.first_discovered_at, b.last_verified_at, b.summary_short, b.why_it_matters,
    b.verification_status, b.importance, b.score, b.pricing, b.is_open_source, b.license,
    b.stars, b.is_hidden_gem,
    coalesce((select array_agg(distinct s.name) from discovery_sources ds join sources s on s.id = ds.source_id
              where ds.discovery_id = b.id), '{}'),
    coalesce((select array_agg(t.name order by t.name) from discovery_tags dt join tags t on t.id = dt.tag_id
              where dt.discovery_id = b.id), '{}'),
    (select bk.status from bookmarks bk where bk.discovery_id = b.id and bk.user_id = auth.uid()),
    count(*) over ()
  from base b
  order by
    case when p_sort = 'relevance' then b.rank end desc nulls last,
    case when p_sort = 'score' then b.score end desc nulls last,
    case when p_sort = 'published' then b.published_at end desc nulls last,
    b.first_discovered_at desc
  limit least(greatest(p_limit, 1), 100) offset greatest(p_offset, 0);
$$;

revoke all on function public.search_discoveries from public, anon;
grant execute on function public.search_discoveries to authenticated;

-- Trending topics backed by real counts: tags seen in the last N days vs the prior window.
create or replace function public.trending_tags(p_days integer default 7, p_limit integer default 12)
returns table (tag text, recent_count bigint, prior_count bigint)
language sql stable security invoker set search_path = public as $$
  select t.name,
    count(*) filter (where d.first_discovered_at >= now() - make_interval(days => p_days)),
    count(*) filter (where d.first_discovered_at <  now() - make_interval(days => p_days)
                       and d.first_discovered_at >= now() - make_interval(days => p_days * 2))
  from discovery_tags dt
  join tags t on t.id = dt.tag_id
  join discoveries d on d.id = dt.discovery_id
  where d.first_discovered_at >= now() - make_interval(days => p_days * 2)
    and d.duplicate_of is null
  group by t.name
  having count(*) filter (where d.first_discovered_at >= now() - make_interval(days => p_days)) >= 2
  order by 2 desc, 1
  limit p_limit;
$$;
revoke all on function public.trending_tags from public, anon;
grant execute on function public.trending_tags to authenticated;

-- Pipeline freshness summary for the overview + settings pages.
create or replace view public.v_pipeline_status with (security_invoker = true) as
select
  (select max(finished_at) from workflow_runs where workflow = 'collect' and status in ('success','partial')) as last_collect_success,
  (select max(finished_at) from workflow_runs where workflow = 'process' and status in ('success','partial')) as last_process_success,
  (select max(first_discovered_at) from discoveries) as newest_discovery_at,
  (select count(*) from discoveries where first_discovered_at >= now() - interval '24 hours') as discoveries_24h,
  (select count(*) from discoveries where processing_status = 'pending') as pending_processing,
  (select count(*) from source_health where status = 'failing') as failing_sources,
  (select count(*) from source_health where status = 'delayed') as delayed_sources,
  (select coalesce(sum(est_cost_usd), 0) from api_usage where created_at >= date_trunc('day', now())) as cost_today_usd,
  (select coalesce(sum(est_cost_usd), 0) from api_usage where created_at >= date_trunc('month', now())) as cost_month_usd;

grant select on public.v_pipeline_status to authenticated;

-- ===== categories (from config/categories.json) =====
insert into public.categories (slug,name,priority,keywords,description) values
('daily-tools','Everyday AI tools',1,ARRAY['assistant','chatbot','productivity','extension','app','launch','ai tool','copilot']::text[],'Tools usable day to day'),
('it-support','IT support & ITSM',2,ARRAY['it support','helpdesk','desktop support','servicenow','itsm','intune','active directory','entra','windows','networking','sysadmin','microsoft 365','o365','powershell','jamf','ticket']::text[],'Desktop support, networking, sysadmin, ITSM'),
('coding','AI coding & development',3,ARRAY['coding','code assistant','ide','python','api','sdk','developer','copilot','cursor','claude code','codex','programming','typescript']::text[],'Coding assistants and app building'),
('agents','Agents, MCP & automation',4,ARRAY['agent','agents','agentic','mcp','model context protocol','browser automation','computer use','workflow','n8n','zapier','automation','rpa']::text[],'Agents, MCP servers, automation'),
('security','AI & IT security',4,ARRAY['vulnerability','cve','security','phishing','malware','ransomware','prompt injection','breach','patch']::text[],'Security relevant to IT work'),
('career','Career & job search',5,ARRAY['resume','interview','job search','career','hiring','linkedin','cover letter','upskilling','certification']::text[],'Career development'),
('productivity','Research & productivity',6,ARRAY['research','notes','data analysis','spreadsheet','excel','summarize','search','deep research','transcription']::text[],'Research, productivity, data'),
('open-source','Open source & self-hosted',7,ARRAY['open source','open-source','self-hosted','selfhosted','local','ollama','llama.cpp','gguf','docker']::text[],'OSS, self-hosted, free alternatives'),
('models','Models & research',8,ARRAY['model','llm','benchmark','paper','arxiv','weights','release','reasoning','multimodal','context window','fine-tuning','deprecation','pricing']::text[],'Model releases and research'),
('industry','Industry news',8,ARRAY['funding','acquisition','regulation','policy','lawsuit','partnership','ipo']::text[],'Major industry developments'),
('creative','Creative AI & frontier tech',9,ARRAY['image','video','audio','music','diffusion','robotics','science','3d','voice','speech']::text[],'Creative AI, robotics, science')
on conflict (slug) do nothing;

-- ===== supabase/seed.sql =====
-- AI RADAR seed: owner allowlist, non-secret settings, one example workflow.
-- Sources and categories live in config/*.json and are synced by `python -m airadar.sync`.
-- IMPORTANT: change the email below to the address you will sign in with.
insert into public.allowed_users (email, role) values (lower('work.ashishkothmeerkar@gmail.com'), 'owner')
on conflict (email) do nothing;

insert into public.app_settings (key, value) values
 ('daily_budget_usd', '0.50'),
 ('summarize_min_score', '35'),
 ('max_items_per_process_run', '60')
on conflict (key) do nothing;

insert into public.workflows (slug, title, objective, tools_required, setup, steps, approx_cost, expected_result, limitations, security_notes, doc_links)
values ('ticket-triage-local-llm',
 'Draft first-response replies for helpdesk tickets with a local LLM',
 'Speed up L1 ticket responses by drafting a reply and suggested category from the ticket text, without sending ticket data to a cloud API.',
 '{Ollama,"A small instruct model (7–8B)","Python 3.11+"}',
 'Install Ollama, pull a small instruct model, and export tickets (subject + description only) to CSV from your ITSM tool.',
 '["Export open tickets to CSV with only non-sensitive fields","Run a short Python script that sends each row to the local Ollama API with a fixed prompt","Write suggested category and draft reply to new CSV columns","Review every draft manually before pasting it into the ticket"]',
 'Free (runs on your own hardware)',
 'A CSV with draft replies and categories you can review in minutes.',
 'Small local models make mistakes; never auto-send. Quality depends on ticket wording.',
 'Remove names, emails, device IDs and passwords from exports. Many employers forbid exporting ticket data at all — check policy first.',
 '{https://github.com/ollama/ollama/blob/main/docs/api.md}')
on conflict (slug) do nothing;
