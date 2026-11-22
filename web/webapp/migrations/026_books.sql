-- The site's books, for the admin screen (0.87.0): what it earned and what it cost.
--
-- sales: each paid minute pack, once (ref is the purchase's own id, as minute_ledger's purchase row holds it), with
-- what was paid in cents, and when it was refunded in full. Its user is set null when the account is deleted, so the
-- money outlives the account (minute_ledger's rows go with it). Backfilled from the ledger at the packs' prices then.
create table sales (
    ref text primary key,
    user_id uuid references users (id) on delete set null,
    at timestamptz not null default now(),
    pack text not null,
    minutes integer not null check (minutes > 0),
    cents integer not null check (cents >= 0),
    refunded_at timestamptz
);
create index sales_at on sales (at);

insert into sales (ref, user_id, at, pack, minutes, cents)
select ref, user_id, at,
       case minutes when 60 then 'hf_minutes_60' when 140 then 'hf_minutes_140' when 320 then 'hf_minutes_320'
                    else 'unknown' end,
       minutes,
       case minutes when 60 then 500 when 140 then 1000 when 320 then 2000 else 0 end
from minute_ledger where kind = 'purchase' and minutes > 0
on conflict (ref) do nothing;

update sales s set refunded_at = l.at
from minute_ledger l where l.kind = 'refund' and l.ref = s.ref and l.user_id = s.user_id;

-- costs: what the site's own OpenRouter key was charged, as OpenRouter reported it: a turn's writing (every model
-- reply in it, the writers' room's too) or a recording's voice. `estimated` where only an estimate was known. Kept
-- when the account is deleted, as sales are.
create table costs (
    id bigserial primary key,
    at timestamptz not null default now(),
    user_id uuid references users (id) on delete set null,
    job_id bigint,
    kind text not null check (kind in ('write', 'voice')),
    usd numeric(12, 6) not null check (usd >= 0),
    estimated boolean not null default false
);
create index costs_at on costs (at);
create index costs_user on costs (user_id);

-- provider_spend: OpenRouter's own count of what the site's key spent on a UTC day (its usage_daily, read through
-- the day and kept at its last reading), to check the costs above against: the difference is spend no turn claimed.
create table provider_spend (
    day date primary key,
    usd numeric(12, 6) not null check (usd >= 0),
    read_at timestamptz not null default now()
);
