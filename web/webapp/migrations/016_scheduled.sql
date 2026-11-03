-- A workout for later: the listener picks a time in the page's sentence, the check-in happens at once, and
-- "Schedule it" queues the turn that writes and records it, due fifteen minutes before. A queued job with
-- not_before in the future waits; its conversation is 'scheduled' until the turn begins.
alter table jobs add column not_before timestamptz;
alter table conversations drop constraint conversations_state_check;
alter table conversations add constraint conversations_state_check
    check (state in ('working', 'waiting', 'idle', 'failed', 'scheduled'));
