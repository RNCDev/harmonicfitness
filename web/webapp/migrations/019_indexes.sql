-- Indexes for the queries that run most (0.76.0): a stream's events by job, the worker's claim of the next queued job
-- (every five seconds in each lane), each listener's queued count (every message), a conversation's job, and the
-- per-user deletes of sessions and links. The tables were small when this was written, so plain create index is
-- quick here (db.migrate runs each file in a transaction, where concurrently can't).
create index if not exists job_events_job on job_events (job_id, id);
create index if not exists jobs_queued on jobs (id) where state = 'queued';
create index if not exists jobs_user_state on jobs (user_id, state);
create index if not exists jobs_finished on jobs (finished_at) where state in ('done', 'failed');
create index if not exists conversations_job on conversations (job_id) where job_id is not null;
create index if not exists sessions_user on sessions (user_id);
create index if not exists sessions_expires on sessions (expires_at);
create index if not exists sign_in_links_user on sign_in_links (user_id);
