-- A listener's photos of their kit, from the message that carries them until the worker's turn reads them (0.83.0):
-- each re-saved without its metadata and sealed with the user's key, taken (read and deleted) as the turn begins, and
-- swept an hour after it came if no turn took it. Never in a job's args, which are kept for days.
create table turn_photos (
    job_id bigint not null references jobs (id) on delete cascade,
    user_id uuid not null references users on delete cascade,
    n integer not null,
    body bytea not null,
    created_at timestamptz not null default now(),
    primary key (job_id, n)
);
create index turn_photos_created on turn_photos (created_at);
