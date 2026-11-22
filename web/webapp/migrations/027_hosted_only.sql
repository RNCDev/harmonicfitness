-- The web app is hosted-only (0.88.0): the site's own OpenRouter key writes and speaks every workout, so the keys
-- listeners stored for their own accounts, and the language model they chose to write with, are never read again.
-- Both go: a stored key is a listener's secret, and nothing should keep one the site no longer uses.
drop table if exists user_keys;
alter table users drop column if exists writer;
