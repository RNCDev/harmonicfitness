create table if not exists schema_migrations (
    name text primary key,
    applied_at timestamptz not null default now()
);

create table users (
    id uuid primary key default gen_random_uuid(),
    email text unique not null,
    wrapped_key bytea not null,
    created_at timestamptz not null default now()
);

create table invites (
    token_hash bytea primary key,
    user_id uuid not null references users on delete cascade,
    expires_at timestamptz not null,
    used_at timestamptz
);

create table sessions (
    token_hash bytea primary key,
    user_id uuid not null references users on delete cascade,
    expires_at timestamptz not null
);

create table context_files (
    user_id uuid references users on delete cascade,
    path text,
    version int not null,
    body bytea not null,
    updated_at timestamptz not null default now(),
    primary key (user_id, path)
);

create table jobs (
    id bigserial primary key,
    user_id uuid not null references users on delete cascade,
    kind text not null,
    args bytea not null,
    state text not null check (state in ('queued', 'running', 'done', 'failed')),
    result bytea,
    error text,
    created_at timestamptz not null default now(),
    started_at timestamptz,
    heartbeat_at timestamptz,
    finished_at timestamptz
);

create unique index one_running_job_per_user on jobs (user_id) where state = 'running';

create table job_events (
    id bigserial primary key,
    job_id bigint not null references jobs on delete cascade,
    at timestamptz not null default now(),
    body bytea not null
);
