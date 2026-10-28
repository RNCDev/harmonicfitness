-- Context file paths sealed like their bodies, and each wrapped data key bound to its user and a
-- key version. Empties every user's data first (approved: Slice 1 held test data only); the
-- cascade clears invites, sessions, context_files, jobs and job_events.
truncate users cascade;

alter table users add column key_version int not null default 1;

-- dropping the plain path drops the primary key with it
alter table context_files drop column path;
alter table context_files add column path_hash bytea not null;   -- HMAC of the path, per user
alter table context_files add column path bytea not null;        -- the path, sealed
alter table context_files add primary key (user_id, path_hash);
