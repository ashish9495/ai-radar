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
