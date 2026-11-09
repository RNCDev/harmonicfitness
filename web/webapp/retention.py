"""What the site stops keeping once nobody can use it (0.76.0): finished jobs a while after they end (their events
go with them), sessions and sign-in links past their time, and the daily allowance's old days. Conversations stay:
`./harmonicfitness pull` can fetch any of them. Run by the worker's main lane at most once a SWEEP_EVERY, beside
media.sweep and clipcache.prune."""
JOB_DAYS = 14        # a finished job (and its events and sealed result) is kept this long for its stream and logs
LINK_DAYS = 1        # a used or expired sign-in link, kept a day past its time
SPEND_DAYS = 30      # the allowance reads only today's row


def sweep(conn) -> dict[str, int]:
    """Delete what has passed its time; {table: rows deleted}. Commits. A job a conversation still names is kept,
    so a conversation never loses the job that last ran it."""
    out = {
        "jobs": conn.execute(
            "delete from jobs j where j.state in ('done', 'failed') "
            "and j.finished_at < now() - make_interval(days => %s) "
            "and not exists (select 1 from conversations c where c.job_id = j.id)", (JOB_DAYS,)).rowcount,
        "sessions": conn.execute("delete from sessions where expires_at < now()").rowcount,
        "sign_in_links": conn.execute("delete from sign_in_links where expires_at < now() - make_interval(days => %s)",
                                      (LINK_DAYS,)).rowcount,
        "spend": conn.execute("delete from spend where day < current_date - %s", (SPEND_DAYS,)).rowcount,
    }
    conn.commit()
    return out
