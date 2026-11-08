-- A workout's MP3 (one with a build_id) no longer expires: each listener keeps their three newest, and making a
-- fourth deletes the oldest. Its expires_at is null. Any other MP3 (a coach's sample in the chat) still goes after
-- 24 hours.
alter table media alter column expires_at drop not null;
update media set expires_at = null where build_id is not null;
delete from media where build_id is not null and id not in (
    select id from (select id, row_number() over (partition by user_id order by created_at desc, id) as n
                    from media where build_id is not null) newest
    where n <= 3);
