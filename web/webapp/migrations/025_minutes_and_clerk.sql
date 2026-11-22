-- Sign-in through Clerk and recordings paid for in minutes (0.85.0).
--
-- users.clerk_id: the Clerk user this account signs in as (null for an account made with a username and
-- password that hasn't been linked yet). The site still holds no email: Clerk does.
--
-- users.minutes: the balance, never below zero. Every change to it is a row in minute_ledger, written in the
-- same transaction, so the ledger's sum is the balance:
--   grant     +N  the minutes a new account starts with (ref 'welcome'), or an admin's gift
--   purchase  +N  a paid Stripe Checkout session (ref its id), credited once however often the webhook comes
--   record    -N  a recording's hold, taken when Record is pressed (ref the turn's job id); `kept` once its MP3
--                 is stored, `tag` a keyed digest of the workout's folder name (never the name), so the first
--                 time the same script is recorded again costs nothing
--   release   +N  a hold handed back because no MP3 was kept (same ref), once
--   refund    -N  a refunded purchase (ref the Checkout session's id), once
-- No foreign key to jobs: a job row is deleted after a while, and the ledger stays.
alter table users add column clerk_id text unique;
alter table users add column minutes integer not null default 0 check (minutes >= 0);

create table minute_ledger (
    id bigserial primary key,
    user_id uuid not null references users (id) on delete cascade,
    at timestamptz not null default now(),
    kind text not null check (kind in ('grant', 'purchase', 'record', 'release', 'refund')),
    minutes integer not null,
    ref text not null,
    kept boolean not null default false,
    tag text,
    note text,
    unique (user_id, kind, ref)
);
create index minute_ledger_user on minute_ledger (user_id, at desc);
create index minute_ledger_open on minute_ledger (at) where kind = 'record' and not kept;

-- Who has had the minutes an account starts with: a digest of their verified email address, keyed with the
-- site's master key (never the address), so deleting an account and signing up again doesn't give them twice.
create table welcomed (
    who bytea primary key,
    at timestamptz not null default now()
);
