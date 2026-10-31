-- The build that made a workout's MP3 (its build_id, from the build record beside it), so the Logs page can
-- play a logged workout while its MP3 is kept. Null for a coach's sample, an audition candidate, or an MP3
-- kept before this column.
alter table media add column build_id text;
create index media_build on media (user_id, build_id) where build_id is not null;
