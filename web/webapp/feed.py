"""A listener's private podcast feed: an RSS link a podcast app follows, so each new workout lands on the phone.

The link carries a token (32 random bytes, URL-safe base64) and needs no session, since a podcast app can't sign
in. Only its sha256 finds the user; the token is also kept sealed with the user's data key, so Settings can show
the link again. A new link replaces the old one, and turning the feed off forgets both. The feed lists the workout
MP3s the site keeps (the three newest); a podcast app downloads each as it arrives, so the phone keeps them after
the site lets them go. None of these commit: the caller does.
"""
import base64
import datetime
import hashlib
import secrets
import uuid
from email.utils import format_datetime
from xml.sax.saxutils import escape

from . import APP_NAME, crypto
from .store import UserKey

TOKEN = r"[A-Za-z0-9_-]{43}"   # what _token makes: 32 bytes, URL-safe base64 without padding


def _token() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()


def _hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def _aad(uk: UserKey) -> bytes:
    return f"{uk.user_id}:feed".encode()


def url(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/feed/{token}.xml"


def token(conn, uk: UserKey) -> str | None:
    """The listener's feed token, or None while the feed is off."""
    row = conn.execute("select feed_token from users where id = %s", (uk.user_id,)).fetchone()
    if not row or row[0] is None:
        return None
    return crypto.open_(uk.key, bytes(row[0]), _aad(uk)).decode()


def make(conn, uk: UserKey) -> str:
    """A new feed token for the listener, replacing any old one (whose link stops working)."""
    t = _token()
    conn.execute("update users set feed_hash = %s, feed_token = %s where id = %s",
                 (_hash(t), crypto.seal(uk.key, t.encode(), _aad(uk)), uk.user_id))
    return t


def stop(conn, uk: UserKey) -> None:
    """Turn the feed off: its link stops working."""
    conn.execute("update users set feed_hash = null, feed_token = null where id = %s", (uk.user_id,))


def user_for(conn, t: str) -> uuid.UUID | None:
    """The user a feed token belongs to, or None."""
    row = conn.execute("select id from users where feed_hash = %s", (_hash(t),)).fetchone()
    return row[0] if row else None


def episodes(conn, uk: UserKey) -> list[tuple[str, str, int, datetime.datetime]]:
    """(id, name, bytes, made) for each workout MP3 the site keeps, newest first. Never opens one."""
    rows = conn.execute("select id, name, bytes, created_at from media where user_id = %s and build_id is not null "
                        "and (expires_at is null or expires_at > now()) order by created_at desc, id",
                        (uk.user_id,)).fetchall()
    return [(str(i), n, b, c) for i, n, b, c in rows]


def rss(base_url: str, t: str, items: list[tuple[str, str, int, datetime.datetime]]) -> str:
    """The feed's RSS 2.0, with the iTunes tags podcast apps read. Blocked from directories: it's private."""
    base = base_url.rstrip("/")
    title = escape(f"{APP_NAME} workouts")
    about = escape("Your workouts from HarmonicFitness, made fresh each session. This feed is private: "
                   "anyone with its link can hear them.")
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">',
           "<channel>",
           f"<title>{title}</title>",
           f"<link>{escape(base)}/</link>",
           "<language>en</language>",
           f"<description>{about}</description>",
           f"<itunes:summary>{about}</itunes:summary>",
           f"<itunes:author>{escape(APP_NAME)}</itunes:author>",
           f'<itunes:image href="{escape(base)}/podcast-cover.png"/>',
           f"<image><url>{escape(base)}/podcast-cover.png</url><title>{title}</title><link>{escape(base)}/</link></image>",
           '<itunes:category text="Health &amp; Fitness"/>',
           "<itunes:explicit>false</itunes:explicit>",
           "<itunes:type>episodic</itunes:type>",
           "<itunes:block>Yes</itunes:block>"]
    for mid, name, size, made in items:
        enclosure = escape(f"{base}/feed/{t}/{mid}.mp3", {'"': "&quot;"})
        out += ["<item>",
                f"<title>{escape(name)}</title>",
                f'<guid isPermaLink="false">{mid}</guid>',
                f"<pubDate>{format_datetime(made)}</pubDate>",
                f'<enclosure url="{enclosure}" length="{size}" type="audio/mpeg"/>',
                "<itunes:episodeType>full</itunes:episodeType>",
                "</item>"]
    out += ["</channel>", "</rss>", ""]
    return "\n".join(out)
