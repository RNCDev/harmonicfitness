-- The listener's Stop: the worker's heartbeat looks for it every few seconds and kills the job's work.
alter table jobs add column stop_requested boolean not null default false;
