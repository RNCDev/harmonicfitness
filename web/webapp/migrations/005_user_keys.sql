-- Each user's voice service keys, sealed with the user's data key (the service name is the only
-- plain detail beside the ids and the time).
create table user_keys (
    user_id uuid not null references users (id) on delete cascade,
    service text not null,
    secret bytea not null,
    updated_at timestamptz not null default now(),
    primary key (user_id, service)
);
