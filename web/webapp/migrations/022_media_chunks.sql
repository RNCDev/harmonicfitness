-- A workout's MP3 in 1 MB chunks, each sealed on its own, so a player's byte range opens only the chunks it covers
-- and a response streams them one at a time. A row kept before this holds its whole MP3 in media.body (chunk_bytes
-- null) and is read as before until it ages out.
alter table media alter column body drop not null;
alter table media add column chunk_bytes integer;
create table media_chunks (
    media_id uuid not null references media (id) on delete cascade,
    n integer not null,
    body bytea not null,
    primary key (media_id, n)
);
