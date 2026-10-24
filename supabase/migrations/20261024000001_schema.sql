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
