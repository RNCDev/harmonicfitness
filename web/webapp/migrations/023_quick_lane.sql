-- A lane of its own for the quick job (a balance check: what's left on each voice service's account), so it never
-- waits behind a workout's turn. Each lane still runs one job a user at once. A worker from before this release
-- checks every non-enrich kind as one lane, so during a deploy it only waits longer; it never breaks these indexes.
drop index one_running_job_per_user;
create unique index one_running_job_per_user on jobs (user_id)
    where state = 'running' and kind not in ('enrich', 'balances');
create unique index one_running_quick_per_user on jobs (user_id)
    where state = 'running' and kind = 'balances';
