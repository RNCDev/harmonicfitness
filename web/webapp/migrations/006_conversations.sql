-- An agent conversation per row: its history, chat lines, open question and plan live in the
-- sealed body; only the ids, the state, the version and the times are plain. job_id is the turn job
-- that last began a turn, so a conversation left working by a job that died can be failed.
create table conversations (
    id bigserial primary key,
    user_id uuid not null references users (id) on delete cascade,
    state text not null check (state in ('working', 'waiting', 'idle', 'failed')),
    body bytea not null,
    version int not null default 1,
    job_id bigint references jobs on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index conversations_user_updated on conversations (user_id, updated_at desc);
