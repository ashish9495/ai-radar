-- AI RADAR: reliable 5-minute collection, driven by Supabase pg_cron instead of GitHub's schedule.
-- GitHub delays or skips frequent cron schedules; a workflow_dispatch call made every 5 minutes from
-- Supabase starts the collector reliably. Processing then runs automatically after each collection.
--
-- BEFORE RUNNING: replace PASTE_YOUR_GITHUB_TOKEN_HERE (line 14) with your fine-grained GitHub token
-- (repository: ashish9495/ai-radar only; permission: Actions = Read and write). Never commit the token.

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- 1) Store the token encrypted in Supabase Vault (replaces any previous one).
delete from vault.secrets where name = 'github_dispatch_token';
select vault.create_secret('PASTE_YOUR_GITHUB_TOKEN_HERE', 'github_dispatch_token',
                           'AI RADAR: start the Collect sources workflow');

-- 2) Function that asks GitHub to start the collection workflow.
create or replace function public.trigger_collect() returns bigint
language plpgsql security definer set search_path = public as $$
declare
  tok text;
  req bigint;
begin
  select decrypted_secret into tok from vault.decrypted_secrets where name = 'github_dispatch_token';
  if tok is null then raise exception 'github_dispatch_token missing from vault'; end if;
  select net.http_post(
    url     := 'https://api.github.com/repos/ashish9495/ai-radar/actions/workflows/source-collection.yml/dispatches',
    headers := jsonb_build_object(
                 'Authorization', 'Bearer ' || tok,
                 'Accept', 'application/vnd.github+json',
                 'X-GitHub-Api-Version', '2022-11-28',
                 'User-Agent', 'ai-radar-pg-cron',
                 'Content-Type', 'application/json'),
    body    := jsonb_build_object('ref', 'main')
  ) into req;
  return req;
end $$;

-- Only the database itself (pg_cron) may call it; never the website's visitors.
revoke all on function public.trigger_collect() from public, anon, authenticated;

-- 3) Every 5 minutes. (Re-running this file replaces the job.)
select cron.unschedule(jobid) from cron.job where jobname = 'ai-radar-collect';
select cron.schedule('ai-radar-collect', '*/5 * * * *', 'select public.trigger_collect()');

-- 4) Fire once now so you can check it immediately.
select public.trigger_collect() as request_id;

-- To check later:  select status_code, content, created from net._http_response order by created desc limit 5;
--   status_code 204 = GitHub accepted the request.  401 = bad/expired token.  404 = token lacks repo access.
-- To stop:         select cron.unschedule('ai-radar-collect');
