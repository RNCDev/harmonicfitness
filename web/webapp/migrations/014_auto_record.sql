-- Record without asking (Settings): a checked, priced script records at once, within today's allowance,
-- rather than waiting for the Record button. Off unless the listener turns it on.
alter table users add column auto_record boolean not null default false;
