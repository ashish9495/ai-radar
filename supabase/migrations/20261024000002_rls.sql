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
