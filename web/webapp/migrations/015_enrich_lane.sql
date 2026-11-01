-- A lane of its own for enrichment (what a listener's feedback teaches, worked out in the background): an
-- enrich job may run beside a workout's turn, and never blocks one. Each lane still runs one job a user at once.
drop index one_running_job_per_user;
create unique index one_running_job_per_user on jobs (user_id) where state = 'running' and kind <> 'enrich';
create unique index one_running_enrich_per_user on jobs (user_id) where state = 'running' and kind = 'enrich';
