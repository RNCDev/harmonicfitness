-- Each file's SHA-256, sealed with the user's data key (bound to its path), so `sync`'s listing opens 32 bytes a
-- file, not every body. Filled on each write; a row written before this has none, and its body is hashed instead.
alter table context_files add column digest bytea;
