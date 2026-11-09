-- What the page can offer for a failed job (Open Settings), as a code stored beside the words (0.76.0): the page reads
-- the code, and the words can change without taking a button away. Null for a job failed before, or with nothing to
-- offer; codes.of_status falls back to the wording for those.
alter table jobs add column if not exists error_code text;
