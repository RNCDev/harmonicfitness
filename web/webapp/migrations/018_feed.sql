-- A private podcast feed (Settings): a link a podcast app follows, so each new workout arrives on the phone by
-- itself. Only the token's sha256 finds the user; the token itself is sealed with the user's data key, so Settings
-- can show the link again. Null until the listener turns it on; a new link replaces the old one.
alter table users add column feed_hash bytea unique;
alter table users add column feed_token bytea;
