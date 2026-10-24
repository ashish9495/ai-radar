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
