-- The language-model provider the listener chose to write their workouts (a providers.PROVIDERS id), or null:
-- then the first offered provider they have a key for.
alter table users add column writer text;
