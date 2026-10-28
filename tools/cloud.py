"""Cloud voices: the shared core behind each service's engine (tools/services/<name>.py).

A cloud engine is an engine like the local ones: say(text, seed) returns 16-bit mono PCM at
24 kHz, trimmed by the same rule, so everything above it (the lint, the timing layout, the
loudness pass, the MP3, the build record and delivery) doesn't know which engine spoke. It also
takes previous_text= and next_text=, which a service that joins paragraphs uses.

What lives here: the services' settings (knowledge/services.toml), the HTTP call with retries
(standard library only), errors sorted into what the listener must fix (key, payment, quota)
and what a rerun fixes, WAV reading and resampling without numpy, the cost estimate, and a web
coach's voice dict: its saved voice ID on its own service (the service holds the voice; no clip
travels).

The API key is read by the service module at the moment it sends (tools/keys.py), and never
goes into a voice dict, a message, a record or a cache key.
"""
import array
import base64
import binascii
import contextvars
import functools
import hashlib
import http.client
import importlib
import json
import os
import random
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import keys  # noqa: E402
import paths  # noqa: E402
import voice  # noqa: E402
from redact import scrub  # noqa: E402,F401  (cloud.scrub, as before: it lives in the leaf module redact.py)
from services import estimate, rate  # noqa: E402,F401  (they read only services.toml)

SR = 24000
RETRY_STATUS = (429, 500, 502, 503, 504)
TRIES = 6
RATE_WAIT = 120             # seconds: a 429 asking to wait this long or less is retried, whatever its body says
DEADLINE = 300.0            # seconds one request may take in all, its tries and the waits between them
# The local engines' trim rule (engines.TRIM_DB, engines.TRIM_KEEP), which the clip cache's key names. Copied, not
# imported (engines imports this module to speak a web voice), and test_cloud holds the copy to engines' values:
# if the two drifted, paid clips would be trimmed one way and keyed another.
TRIM_DB = -40.0
TRIM_LEVEL = 10 ** (TRIM_DB / 20) * 32767   # in 16-bit samples
TRIM_KEEP = 0.04                            # seconds kept at each end
MIN_AUDIO = 0.1             # seconds: an answer holding less isn't a spoken line
LOCAL_HOSTS = ("127.0.0.1", "localhost")   # where an address override may use plain http (the tests' fakes)
# The stop signal of the render this code runs for: a threading.Event that render sets when it's stopping (no
# retry, no new attempt). One per render, never shared: stop_on sets it in the render's own context, and
# speaker() carries it into the worker threads that speak.
_stop = contextvars.ContextVar("harmonicfitness_stop", default=None)


class ServiceError(Exception):
    """A service said no. kind: auth, billing, quota (the listener must act), bad_request, unavailable."""

    def __init__(self, kind, service, message, status=None):
        super().__init__(message)
        self.kind, self.service, self.message, self.status = kind, service, message, status

    def __str__(self):
        name = services().get(self.service, {}).get("name", self.service or "The service")
        return scrub(f"{name}: {self.message}")

    @property
    def listener_must_act(self):
        return self.kind in ("auth", "billing", "quota")

    @property
    def exit_code(self):
        """What a tool exits with when this stops it (cli.run): 4 when the listener must act, else 1."""
        return errors.SERVICE if self.listener_must_act else errors.ISSUES


def service_name(service):
    """The service's name as people say it (Fish Audio, ElevenLabs...), or the id itself for one we don't know."""
    return services().get(service, {}).get("name", service or "no service")


def services():
    """{service: settings} from knowledge/services.toml (read once, by the services package)."""
    import services as service_modules
    return service_modules.settings()


SERVICES = tuple(services())   # the web services, in services.toml's order: the one list of them
ROUTES = ("local", *SERVICES)  # every route: this computer's own engine, then each web service


def base_url(service):
    """The service's API address. HARMONICFITNESS_<SERVICE>_URL points it elsewhere (the tests' fake servers), but only
    at an https:// address or this computer (127.0.0.1, localhost): a stray setting never sends a key in the
    clear, or anywhere off this machine unencrypted."""
    var = f"HARMONICFITNESS_{service.upper()}_URL"
    override = os.environ.get(var)
    if override:
        parts = urllib.parse.urlsplit(override)
        if parts.scheme.lower() != "https" and (parts.scheme.lower() != "http" or parts.hostname not in LOCAL_HOSTS):
            raise ServiceError("bad_request", service, f"{var} is set to an address that isn't https:// or this "
                                                       f"computer, so nothing was sent: unset it")
        return override.rstrip("/")
    return services()[service]["url"].rstrip("/")


def _message(body):
    """A refusal's reason, from its body: scrubbed of every key before it's cut to 300 characters, so a key
    cut in half can't slip through."""
    text = scrub(body.decode("utf-8", "replace"))
    try:
        data = json.loads(text)
    except ValueError:
        return text.strip()[:300] or "no reason given"
    if isinstance(data, dict):
        detail = data.get("detail")
        for value in (data.get("message"), detail.get("message") if isinstance(detail, dict) else detail,
                      data.get("err_msg"), data.get("title"), data.get("error")):
            if isinstance(value, str) and value.strip():
                return value.strip()[:300]
            if isinstance(value, list) and value:
                return str(value[0].get("msg", value[0]) if isinstance(value[0], dict) else value[0])[:300]
    return json.dumps(data)[:300]


def _kind(status, body):
    text = body.decode("utf-8", "replace").lower()
    if "quota" in text:
        return "quota"
    if status == 402 or (400 <= status < 500 and ("insufficient_credits" in text or "payment" in text)):
        return "billing"   # a 5xx page that mentions payment is still an outage
    if status in (401, 403):
        return "auth"
    if status in RETRY_STATUS:
        return "unavailable"
    return "bad_request"


def stop_on(event):
    """From now on (until stop_on(None)), in this thread's context, `event` being set stops every request's
    retries: a render that failed or was interrupted sends nothing more, and a worker waiting out a backoff wakes
    at once. A speaker made after this call carries the event into whichever thread runs it; another render,
    in another thread, keeps its own."""
    _stop.set(event)


def stopping(stop=None):
    stop = stop if stop is not None else _stop.get()
    return stop is not None and stop.is_set()


def _wait_seconds(attempt, retry_after):
    """How long to wait before the next try: Retry-After when it's a number, else backoff with jitter."""
    scale = float(os.environ.get("HARMONICFITNESS_RETRY_WAIT", "1"))   # the tests set 0
    try:
        seconds = float(retry_after) if retry_after else min(2 ** attempt, 30) * (0.75 + random.random() / 2)
    except ValueError:
        seconds = min(2 ** attempt, 30)
    return seconds * scale


def _wait(seconds, sleep, stop=None):
    if sleep is None:   # the default: wait, but wake as soon as the render stops
        if stop is not None:
            stop.wait(seconds)
        else:
            time.sleep(seconds)
    else:
        sleep(seconds)


def _seconds(retry_after):
    """Retry-After as seconds, or None when it isn't a number (an HTTP date, or absent)."""
    try:
        return float(retry_after) if retry_after is not None else None
    except ValueError:
        return None


def _short(retry_after):
    try:
        return retry_after is not None and 0 <= float(retry_after) <= RATE_WAIT
    except ValueError:
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """None of the services' APIs redirects, and following one would send the key to wherever it points."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = urllib.parse.urlsplit(newurl).hostname or newurl[:80]
        fp.close()
        raise ServiceError("unavailable", getattr(req, "harmonicfitness_service", None),
                           f"redirected to {host}; not followed (HTTP {code})", status=code)


def _open(req, timeout):
    """The answer to `req`, through an opener that never follows a redirect (plain http stays, for the fakes)."""
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=_tls()))
    return opener.open(req, timeout=timeout)


def request(method, url, headers, body, timeout=60, service=None, tries=TRIES, sleep=None, idempotent=True,
            deadline=DEADLINE):
    """(status, headers, body) for a 2xx answer. Rate limits, server errors and dropped connections are
    retried with backoff (honoring Retry-After); anything else raises ServiceError with the service's reason.
    A request that saves something (idempotent=False: a saved voice, a stored design) is retried only when
    the service can't have acted on it: a 429, or a connection refused before anything was sent. A server
    error or a timeout after sending could have saved it, and a retry would save a second one. Once a render
    is stopping (stop_on), nothing more is sent. A redirect is never followed: it raises ServiceError.
    `deadline` bounds the whole call, every try and every wait (a slow service holds the render lock): each try
    gets at most what's left of it, and a wait that would outlast it raises ServiceError("unavailable")."""
    last = None
    stop = _stop.get()
    start = time.monotonic()

    def out_of_time():
        why = f"; the last try: {last.message}" if last else ""
        return ServiceError("unavailable", service, f"no answer within {deadline:g}s{why}",
                            status=last.status if last else None)
    for attempt in range(tries):
        if stopping(stop):
            raise last or ServiceError("unavailable", service, "not sent: the render is stopping")
        left = deadline - (time.monotonic() - start)
        if left <= 0:
            raise out_of_time()
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        req.harmonicfitness_service = service
        try:
            with _open(req, min(timeout, left)) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            data = e.read() or b""
            kind = _kind(e.code, data)
            last = ServiceError(kind, service, f"{_message(data)} (HTTP {e.code})", status=e.code)
            retry_after = e.headers.get("Retry-After") if e.headers else None
            if e.code == 429 and _seconds(retry_after) is not None and not _short(retry_after):
                # asked to wait longer than a rate limit ever does: the quota is used up, and sleeping an hour
                # (or five) in a build helps nobody
                raise ServiceError("quota", service, f"asked to wait {_seconds(retry_after):.0f} seconds before the "
                                   f"next request ({_message(data)}; HTTP 429): the quota is used up for now",
                                   status=429) from None
            # A 429 asking for a short wait is a rate limit, even when its body says "quota" (Google-style APIs).
            # So is one that names no wait at all: it's retried with backoff, and only a 429 that outlasts every
            # try is reported as the quota (the last error raised below).
            rate_limited = e.code == 429 and (_short(retry_after) or retry_after is None)
            limited = rate_limited or (e.code == 429 and kind == "unavailable")
            if not rate_limited and (e.code not in RETRY_STATUS or kind != "unavailable"):
                raise last from None
            if not idempotent and not limited:
                raise last from None
        except (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError, http.client.HTTPException) as e:
            # HTTPException: a cut-off answer (IncompleteRead) or a garbled status line, which isn't an OSError
            reason = getattr(e, "reason", e)
            last = ServiceError("unavailable", service, f"couldn't reach the service ({reason})")
            retry_after = None
            if not idempotent and not isinstance(reason, (ConnectionRefusedError, socket.gaierror)):
                raise last from None
        except (ValueError, UnicodeEncodeError) as e:   # the request couldn't be built: a header value the
            var = keys.SERVICE_VARS.get(service, "the key")   # client refuses carries the key, so never echo it
            if "header" in str(e).lower() and paths.WEB:
                raise ServiceError("auth", service, f"the key couldn't be sent as a request header (a stray "
                                   f"character in it?): re-paste it in {keys.APP_SETTINGS}") from None
            if "header" in str(e).lower():
                raise ServiceError("auth", service, f"the key couldn't be sent as a request header (a stray character "
                                   f"in it?): re-paste it after {var}= (./harmonicfitness keys open)") from None
            raise ServiceError("bad_request", service, f"the request couldn't be built: {scrub(str(e))}") from None
        if attempt < tries - 1 and not stopping(stop):
            seconds = _wait_seconds(attempt, retry_after)
            if seconds > deadline - (time.monotonic() - start):
                raise out_of_time()
            _wait(seconds, sleep, stop)
    raise last


def json_answer(data, service, what="the answer"):
    """A 2xx answer's JSON object. A body that isn't one (cut off, HTML, a list) raises ServiceError, so it
    stops like any refusal instead of as a traceback. `what` names it in the message."""
    try:
        answer = json.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
    except (ValueError, UnicodeDecodeError):
        answer = None
    if not isinstance(answer, dict):
        text = data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)
        raise ServiceError("bad_request", service, f"{what} couldn't be read (not a JSON object: "
                           f"{scrub(text.strip()[:120]) or 'empty'})")
    return answer


def saved_what(service, name):
    """How json_answer names a save's answer: the voice may be saved even though its answer can't be read."""
    return f"the saved voice's answer (the voice may be saved at {service_name(service)}: look for \"harmonicfitness {name}\")"


def b64_audio(text, service):
    """The bytes of base64 audio in a JSON answer; ServiceError when it isn't base64."""
    try:
        return base64.b64decode(text or "", validate=False)
    except (binascii.Error, ValueError, TypeError) as e:
        raise ServiceError("bad_request", service, f"the answer's audio isn't base64 ({e})") from None


@functools.cache
def _tls():
    """One TLS context per process (loading the certificate bundle for every request is slow)."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except (ImportError, OSError) as e:   # CI and the fake servers (plain HTTP) don't need it; a real request says so
        print(f"(No certificate bundle from certifi ({type(e).__name__}): using the system's certificates.)",
              file=sys.stderr)
        return None


def wav_pcm(data):
    """(16-bit mono PCM, sample rate) from WAV bytes. Reads the data chunk to the end of the bytes when
    its size is a placeholder (Fish streams WAV with sizes it can't know yet); mixes stereo to mono."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a WAV file")
    i, rate, channels, bits = 12, SR, 1, 16
    while i + 8 <= len(data):
        cid, size = data[i:i + 4], int.from_bytes(data[i + 4:i + 8], "little")
        start = i + 8
        if cid == b"fmt ":
            channels = int.from_bytes(data[start + 2:start + 4], "little")
            rate = int.from_bytes(data[start + 4:start + 8], "little")
            bits = int.from_bytes(data[start + 14:start + 16], "little")
        elif cid == b"data":
            pcm = data[start:start + size] if start + size <= len(data) else data[start:]
            if bits != 16:
                raise ValueError(f"{bits}-bit WAV; expected 16-bit")
            if channels < 1 or rate < 1:
                raise ValueError(f"a WAV of {channels} channel(s) at {rate} Hz")
            pcm = pcm[:len(pcm) - len(pcm) % (2 * channels)]
            if channels > 1:
                s = array.array("h", pcm)
                if sys.byteorder == "big":
                    s.byteswap()
                mono = array.array("h", (int(sum(s[j:j + channels]) / channels) for j in range(0, len(s), channels)))
                if sys.byteorder == "big":
                    mono.byteswap()
                pcm = mono.tobytes()
            return bytes(pcm), rate
        i = start + size + (size & 1)
    raise ValueError("no audio in the WAV")


def wav_bytes(pcm, rate=SR):
    """A WAV file's bytes holding 16-bit mono PCM."""
    import wav
    return wav.wav_bytes(pcm, rate)


def _samples(pcm):
    s = array.array("h", pcm[:len(pcm) - len(pcm) % 2])
    if sys.byteorder == "big":
        s.byteswap()
    return s


def _bytes(samples):
    if sys.byteorder == "big":
        samples.byteswap()
    return samples.tobytes()


def resample(pcm, src, dst):
    """Linear resampling of 16-bit mono PCM; plenty for speech going into a 96 kbit/s MP3."""
    if src == dst:
        return pcm
    s = _samples(pcm)
    n = int(round(len(s) * dst / src))
    if not s or not n:
        return b""
    step = (len(s) - 1) / max(n - 1, 1)
    out = array.array("h", bytes(2 * n))
    for j in range(n):
        x = j * step
        k = int(x)
        frac = x - k
        a = s[k]
        b = s[k + 1] if k + 1 < len(s) else a
        out[j] = int(a + (b - a) * frac)
    return _bytes(out)


def trim(pcm):
    """The local engines' rule: cut lead-in and tail silence below -40 dB, keeping 40 ms at each end."""
    s = _samples(pcm)
    first = next((j for j in range(len(s)) if abs(s[j]) > TRIM_LEVEL), None)
    if first is None:
        return pcm
    last = next(j for j in range(len(s) - 1, -1, -1) if abs(s[j]) > TRIM_LEVEL)
    keep = int(TRIM_KEEP * SR)
    return _bytes(s[max(first - keep, 0):last + keep])


def content_type(headers):
    """A response's Content-Type (its media type, lowercased, without parameters), or None when it names none.
    Header names are matched in any case."""
    for k, v in (headers or {}).items():
        if k.lower() == "content-type" and v:
            return v.split(";")[0].strip().lower() or None
    return None


def _raw_ok(content_type):
    """Whether a reply of this content type may be raw PCM: an audio type, plain bytes, or none named (a
    service's base64 audio inside JSON carries no type of its own)."""
    return content_type is None or content_type.startswith("audio/") or content_type == "application/octet-stream"


def audio_pcm(data, rate_hint=SR, service=None, *, expect="wav", content_type=None):
    """16-bit mono PCM at 24 kHz from what a service sent, proven to be audio. `expect` is what was asked for:
    "wav", "mp3" or "pcm" (raw 16-bit mono at rate_hint); `content_type` the reply's (content_type(headers)),
    or None for audio that came inside JSON. A WAV is read, MP3 and the like go through ffmpeg, and raw PCM is
    taken only when raw PCM was asked for and the reply is typed as audio or bytes. Anything else (text, a
    compressed or cut-off stream, a WAV that can't be read, under MIN_AUDIO of sound) raises ServiceError:
    never cached as noise, paid for once and replayed in every build."""
    head = data[:64].lstrip()
    if not data or head[:1] in (b"{", b"[", b"<"):
        raise ServiceError("bad_request", service, "the service answered with text, not audio: "
                           + _message(data)[:200] if data else "the service answered with no audio")
    if data[:4] == b"RIFF":
        try:
            pcm, rate = wav_pcm(data)
        except (ValueError, IndexError) as e:
            raise ServiceError("bad_request", service, f"the service's WAV couldn't be read ({e})") from None
        pcm = resample(pcm, rate, SR)
    elif data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2") or data[:4] in (b"OggS", b"fLaC"):
        import ffmpeg
        if not ffmpeg.exe():   # the listener's to fix (setup), not the service's
            return ffmpeg_pcm(data, "A service sent compressed audio")
        try:
            pcm = ffmpeg_pcm(data, "A service sent compressed audio")
        except errors.RenderStopped as e:
            raise ServiceError("bad_request", service, f"its audio couldn't be read: {e}") from None
    elif expect == "pcm" and _raw_ok(content_type):
        pcm = resample(data[:len(data) - len(data) % 2], rate_hint, SR)   # raw PCM, as asked for
    else:
        sent = f" ({content_type})" if content_type else ""
        raise ServiceError("bad_request", service, f"the service's answer{sent} isn't audio it can read: "
                           f"{expect.upper()} was asked for")
    if len(pcm) < 2 * int(MIN_AUDIO * SR):
        raise ServiceError("bad_request", service, f"the service answered with {len(pcm) / 2 / SR:.2f}s of audio, "
                           "too little to be a spoken line")
    return pcm


def ffmpeg_pcm(data, what="The audio"):
    """16-bit mono PCM at 24 kHz from any audio file's bytes, through ffmpeg. A file ffmpeg can't read stops
    with the end of what it said."""
    import ffmpeg
    exe = ffmpeg.exe()
    if not exe:
        raise errors.RenderStopped(f"{what}, which needs ffmpeg to read: rerun ./harmonicfitness setup.")
    try:
        out = ffmpeg.run([exe, "-loglevel", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", str(SR),
                          "pipe:1"], "read it", 300, input=data)
    except errors.RenderStopped as e:
        raise errors.RenderStopped(f"{what}, and {e}") from None
    if not out.stdout:
        raise errors.RenderStopped(f"{what}, and ffmpeg found no audio in it.")
    return out.stdout


VOICE_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}")   # what every service hands back


def web_key(p, model):
    """A web coach's identity in every pace and cache key: its service, voice, `model`, style and settings."""
    settings = json.dumps(p.table("settings"), sort_keys=True)
    raw = f"{p.service or ''}|{p.voice_id or ''}|{model}|{p.style}|{settings}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def voice_for(p, route=None, pending=False):
    """The voice dict for web coach `p`: its saved voice on its own service (`route` is ignored; a web coach
    speaks only through the service that made it). No key in it, and no clip: the service holds the voice.
    With `pending`, a coach still to be made (no voice yet) gets a voice dict with no voice ID, for the
    lint's and the brief's estimated pace only; nothing renders from it."""
    if not p.is_web:
        raise errors.CoachError(f"{p.name} is a local coach: a local coach renders only locally.")
    service = p.service
    if service not in services():
        raise errors.CoachError(f"{p.name} names no known web service ({service or 'none'}); "
                         f"the services: {', '.join(services())}.")
    if not p.voice_id and not (pending and p.pending):
        raise errors.CoachError(f"{p.name} has no voice yet" + (f" ({p.pending} pending)" if p.pending else "")
                         + ": audition one and keep it (the coach skill).")
    if p.voice_id and not VOICE_ID.fullmatch(p.voice_id):
        raise errors.CoachError(f"{p.name}'s voice_id in {p.folder}/persona.md isn't a voice ID a service gives "
                                "(letters, digits and _ . : - only): copy it again from the service.")
    s = services()[service]
    model = p.model or s["default_model"]
    return voice.WebVoice(
        name=p.name, persona=p.slug, persona_dir=p.folder, engine=service, backend="cloud", route=service,
        service=service, model=model, voice_id=p.voice_id, style=p.style, revision=None, generate={},
        pace_file=p.pace_file, concurrency=int(s.get("concurrency") or 1), max_chars=int(s.get("max_chars") or 0),
        key=web_key(p, model)).as_dict()


def service_module(name):
    """The module that speaks to web service `name` (tools/services/<name>.py, the contract in
    tools/services/__init__.py): the one place a service is looked up by name."""
    if name not in SERVICES:
        raise errors.CoachError(f"No web service '{name}': the services are {', '.join(SERVICES)}.")
    return importlib.import_module(f"services.{name}")


def speaker(voice):
    """say(text, seed, previous_text=None, next_text=None) for the voice's service. It carries the stop signal
    in force here (stop_on) into whatever thread calls it, so a render's workers stop with that render alone."""
    say = service_module(voice["service"]).speaker(voice)
    stop = _stop.get()

    def carried(*args, **kwargs):
        token = _stop.set(stop)
        try:
            return say(*args, **kwargs)
        finally:
            _stop.reset(token)
    return carried


def key_or_stop(service):
    value = keys.get(service)
    if not value and paths.WEB:
        raise ServiceError("auth", service, f"no key yet: add your {service_name(service)} key in {keys.APP_SETTINGS}")
    if not value:
        raise ServiceError("auth", service, f"no key on this computer: ./harmonicfitness keys init {service}, then paste "
                                            f"the key into me/.env after {keys.SERVICE_VARS[service]}=")
    return value


def path_part(value):
    """`value` (a voice ID read from an editable file) made safe as one segment of a URL path: a stray / or ..
    can't reach another endpoint."""
    return urllib.parse.quote(str(value), safe="")


def multipart(fields, files):
    """(body, content type) for a multipart/form-data upload: `fields` {name: text}, `files`
    [(field, filename, bytes, content type)]."""
    import uuid
    boundary = "harmonicfitness-" + uuid.uuid4().hex
    out = bytearray()
    for name, value in fields.items():
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n").encode()
    for field, filename, data, ctype in files:
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\n"
                f"Content-Type: {ctype}\r\n\r\n").encode() + data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def delete(service, url, headers):
    """DELETE a saved voice: True when the service removed it, or it was already gone (a 404). Any other
    refusal raises ServiceError."""
    try:
        request("DELETE", url, headers, None, service=service)
    except ServiceError as e:
        if e.status == 404:
            return True
        raise
    return True


def find_audio(answer):
    """(base64 audio, MIME type) from anywhere in a JSON answer: the first dict holding a `data` string,
    preferring one whose MIME type says audio. (None, None) when there's none."""
    found = []

    def walk(x):
        if isinstance(x, dict):
            data = x.get("data")
            if isinstance(data, str) and data:
                mime = str(x.get("mime_type") or x.get("mimeType") or "")
                found.append((data, mime))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(answer)
    audio = [f for f in found if f[1].startswith("audio")]
    return (audio or found or [(None, None)])[0]


def mime_rate(mime, default=SR):
    """The sample rate a MIME type names ("audio/L16;codec=pcm;rate=24000"), else `default`."""
    import re
    m = re.search(r"rate=(\d+)", mime or "")
    return int(m.group(1)) if m else default
