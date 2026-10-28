alter table sessions add column renewed_at timestamptz not null default now();
