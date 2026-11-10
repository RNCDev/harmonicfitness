-- Each file's SHA-256, sealed with the user's data key (bound to its path and the version it was written at), so
-- `sync`'s listing opens 32 bytes a file, not every body. Filled on each write. A row written before this has none,
-- and one a 0.76.2 process writes during a deploy keeps a digest of the version before: neither opens at the row's
-- version, so its body is hashed instead.
alter table context_files add column digest bytea;
