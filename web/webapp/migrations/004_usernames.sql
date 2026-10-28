-- Username and password accounts replace invites. Existing users keep their files: each gets a
-- username from their email's local part (a short id added on a clash or when too short) and no
-- password, which the app asks them to set. One-time links stay, for adding a device and for a
-- forgotten password; unused invites are dropped.
alter table users add column username text;
alter table users add column password_hash text;

with base as (
    select id, regexp_replace(lower(split_part(email, '@', 1)), '[^a-z0-9_.-]', '', 'g') as name,
           created_at
    from users
), ok as (
    select id, case when name ~ '^[a-z0-9][a-z0-9_.-]{2,23}$' then name
                    else 'user-' || left(replace(id::text, '-', ''), 8) end as name,
           created_at
    from base
), ranked as (
    select id, name, row_number() over (partition by name order by created_at, id) as n from ok
)
update users u
set username = case when r.n = 1 then r.name
                    else r.name || '-' || left(replace(u.id::text, '-', ''), 6) end
from ranked r where r.id = u.id;

alter table users alter column username set not null;
alter table users add constraint users_username_key unique (username);
alter table users drop column email;

alter table invites rename to sign_in_links;
delete from sign_in_links where used_at is null;
