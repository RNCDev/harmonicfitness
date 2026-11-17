"""A listener's photos of their kit (0.83.0): looked at, never kept.

A message may carry up to MOST photos. Each is re-saved here before anything is stored: decoded, turned upright,
shrunk to EDGE pixels on its longer side and written again as a plain JPEG, so its metadata (where it was taken,
the phone, the time) never goes further than this module. The page shrinks and re-saves them too; this is the copy
that holds whatever sent them. They wait in `turn_photos`, sealed with the user's key, only until the turn that
reads them begins: `take` reads and deletes them in one statement, and `sweep` deletes any an hour old that no turn
took. They never enter a job's args, the conversation or its history (the agent keeps a line in their place).

Transactions, as everywhere in webapp/: these never commit; the caller does.
"""
import base64
import binascii
import io

from . import crypto
from .store import UserKey

MOST = 3                 # photos in one message: a few corners of a room, as the setup skill asks for
RAW_MOST = 3_000_000     # bytes of one photo as sent (the page sends about half a megabyte)
EDGE = 1600              # pixels on the longer side, kept: enough to read the numbers on a dumbbell
PIXELS_MOST = 40_000_000  # pixels decoded at most: a larger image is refused before it's drawn
KEEP_MINUTES = 60        # a photo no turn took is deleted this long after it came
MEDIA_TYPE = "image/jpeg"
FORMATS = ("JPEG", "PNG", "WEBP")


class Refused(Exception):
    """A photo that can't be used; `message` says why, in the listener's words."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def decode(sent: str) -> bytes:
    """A photo as the page sends it (base64, optionally a data: URL), as bytes."""
    if sent.startswith("data:"):
        sent = sent.partition(",")[2]
    try:
        raw = base64.b64decode(sent, validate=True)
    except (binascii.Error, ValueError):
        raise Refused("A photo didn't arrive whole. Try adding it again.") from None
    if not raw or len(raw) > RAW_MOST:
        raise Refused(f"A photo is over {RAW_MOST // 1_000_000} MB. Try a smaller one.")
    return raw


def clean(raw: bytes) -> bytes:
    """The photo re-saved: upright, at most EDGE pixels on its longer side, a plain JPEG with no metadata. Refused
    for anything but a JPEG, PNG or WebP image, or one too large to decode safely."""
    from PIL import Image, ImageOps   # the web process only: the engine never needs it
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format not in FORMATS:
                raise Refused("Photos need to be JPEG, PNG or WebP.")
            if im.width * im.height > PIXELS_MOST:
                raise Refused("A photo is too large to read. Try a smaller one.")
            im = ImageOps.exif_transpose(im)   # upright before the orientation tag is left behind
            im = im.convert("RGB")
            im.thumbnail((EDGE, EDGE))
            out = io.BytesIO()
            im.save(out, "JPEG", quality=85, optimize=True)   # no exif=, icc_profile= or comment: none carried over
            return out.getvalue()
    except Refused:
        raise
    except (OSError, ValueError, Image.DecompressionBombError):
        raise Refused("That file isn't a photo that can be read. Try another.") from None


def prepared(sent: list[str] | None) -> list[bytes]:
    """The message's photos, each decoded and re-saved; Refused names the first that can't be used."""
    sent = sent or []
    if len(sent) > MOST:
        raise Refused(f"Up to {MOST} photos in one message.")
    return [clean(decode(s)) for s in sent]


def _aad(uk: UserKey, job_id: int, n: int) -> bytes:
    return f"{uk.user_id}:turn_photos:{job_id}:{n}".encode()


def add(conn, uk: UserKey, job_id: int, photos: list[bytes]) -> None:
    """Keep a turn's photos, sealed, until its turn takes them."""
    for n, body in enumerate(photos):
        conn.execute("insert into turn_photos (job_id, user_id, n, body) values (%s, %s, %s, %s)",
                     (job_id, uk.user_id, n, crypto.seal(uk.key, body, _aad(uk, job_id, n))))


def take(conn, uk: UserKey, job_id: int) -> list[bytes]:
    """A turn's photos, in the order sent, deleted as they're read: none, once taken or swept."""
    rows = conn.execute("delete from turn_photos where job_id = %s and user_id = %s returning n, body",
                        (job_id, uk.user_id)).fetchall()
    return [crypto.open_(uk.key, bytes(body), _aad(uk, job_id, n)) for n, body in sorted(rows)]


def sweep(conn) -> int:
    """Delete the photos no turn took within KEEP_MINUTES; how many."""
    return conn.execute("delete from turn_photos where created_at < now() - make_interval(mins => %s)",
                        (KEEP_MINUTES,)).rowcount
