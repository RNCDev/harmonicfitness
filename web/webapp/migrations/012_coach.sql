-- The coach the listener chose on the web app (a coach's folder name), and the listener's own day it was chosen:
-- the first screen's coach until a workout logged on a later day used another. Null: the coach used last.
alter table users add column coach text;
alter table users add column coach_day date;
