-- What each listener's approved recordings may send to a voice service each day (characters), and the
-- recorded clips kept a week so a re-record pays only for lines that changed (sealed; the path is the
-- engine's cache file name, a hash).
create table spend (
    user_id uuid not null references users (id) on delete cascade,
    day date not null,
    chars integer not null default 0,
    primary key (user_id, day)
);
create table clip_cache (
    user_id uuid not null references users (id) on delete cascade,
    path text not null,
    body bytea not null,
    bytes integer not null,
    used_at timestamptz not null default now(),
    primary key (user_id, path)
);
create index clip_cache_used on clip_cache (used_at);
