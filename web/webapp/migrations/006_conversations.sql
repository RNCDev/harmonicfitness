-- An agent conversation per row: its history, chat lines, open question and plan live in the
-- sealed body; only the ids, the state, the version and the times are plain.
create table conversations (
    id bigserial primary key,
    user_id uuid not null references users (id) on delete cascade,
    state text not null check (state in ('working', 'waiting', 'idle', 'failed')),
    body bytea not null,
    version int not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index conversations_user_updated on conversations (user_id, updated_at desc);
