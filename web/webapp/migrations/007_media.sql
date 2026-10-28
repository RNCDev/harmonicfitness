-- A workout's MP3, kept 24 hours for the listener to play or download: sealed with the user's data key
-- (the name and the times are plain). The worker deletes rows past expires_at.
create table media (
    id uuid primary key,
    user_id uuid not null references users (id) on delete cascade,
    name text not null,
    body bytea not null,
    bytes integer not null,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null
);
create index media_expires on media (expires_at);
