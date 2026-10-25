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
import importlib
import json
import os
import random
import socket
import sys
import time
import tomllib
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import paths  # noqa: E402

SR = 24000
SERVICES_FILE = os.path.join(paths.ROOT, "knowledge", "services.toml")
RETRY_STATUS = (429, 500, 502, 503, 504)
TRIES = 6
RATE_WAIT = 120             # seconds: a 429 asking to wait this long or less is retried, whatever its body says
TRIM_LEVEL = 0.01 * 32767   # engines.TRIM_DB (-40 dB) in 16-bit samples
TRIM_KEEP = 0.04            # seconds kept at each end, as engines.TRIM_KEEP
_settings = None


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
        return cli.SERVICE if self.listener_must_act else cli.ISSUES


def service_name(service):
    """The service's name as people say it (Fish Audio, ElevenLabs...), or the id itself for one we don't know."""
    return services().get(service, {}).get("name", service or "no service")


def scrub(text):
    """`text` with every key value set here (the environment's or me/.env's) replaced by <key>, so nothing a
    library or a service echoes can print one."""
    import keys
    for value in sorted(keys.raw_values(), key=len, reverse=True):
        for form in (value, value.strip()):
            if len(form) >= 8:
                text = text.replace(form, "<key>")
    return text


def services():
    """{service: settings} from knowledge/services.toml."""
    global _settings
    if _settings is None:
        with open(SERVICES_FILE, "rb") as f:
            data = tomllib.load(f)
        _settings = {k: dict(v, rates_checked=data.get("rates_checked")) for k, v in data.items() if isinstance(v, dict)}
    return _settings


def base_url(service):
    """The service's API address; SWEATCAST_<SERVICE>_URL points it elsewhere (the tests' fake servers)."""
    return (os.environ.get(f"SWEATCAST_{service.upper()}_URL") or services()[service]["url"]).rstrip("/")


def _message(body):
    try:
        data = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return body.decode("utf-8", "replace").strip()[:300] or "no reason given"
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


def _wait(attempt, retry_after, sleep):
    scale = float(os.environ.get("SWEATCAST_RETRY_WAIT", "1"))   # the tests set 0
    try:
        seconds = float(retry_after) if retry_after else min(2 ** attempt, 30) * (0.75 + random.random() / 2)
    except ValueError:
        seconds = min(2 ** attempt, 30)
    sleep(seconds * scale)


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


def request(method, url, headers, body, timeout=60, service=None, tries=TRIES, sleep=time.sleep, idempotent=True):
    """(status, headers, body) for a 2xx answer. Rate limits, server errors and dropped connections are
    retried with backoff (honoring Retry-After); anything else raises ServiceError with the service's reason.
    A request that saves something (idempotent=False: a saved voice, a stored design) is retried only when
    the service can't have acted on it: a 429, or a connection refused before anything was sent. A server
    error or a timeout after sending could have saved it, and a retry would save a second one."""
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_tls()) as r:
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
            limited = e.code == 429 and (_short(retry_after) or kind == "unavailable")
            if not (e.code == 429 and _short(retry_after)) and (e.code not in RETRY_STATUS or kind != "unavailable"):
                raise last from None
            if not idempotent and not limited:
                raise last from None
        except (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError) as e:
            reason = getattr(e, "reason", e)
            last = ServiceError("unavailable", service, f"couldn't reach the service ({reason})")
            retry_after = None
            if not idempotent and not isinstance(reason, (ConnectionRefusedError, socket.gaierror)):
                raise last from None
        except (ValueError, UnicodeEncodeError) as e:   # the request couldn't be built: a header value the
            import keys                                   # client refuses carries the key, so never echo it
            var = keys.SERVICE_VARS.get(service, "the key")
            if "header" in str(e).lower():
                raise ServiceError("auth", service, f"the key couldn't be sent as a request header (a stray character "
                                   f"in it?): re-paste it after {var}= (./sweatcast keys open)") from None
            raise ServiceError("bad_request", service, f"the request couldn't be built: {scrub(str(e))}") from None
        if attempt < tries - 1:
            _wait(attempt, retry_after, sleep)
    raise last


def _tls():
    try:
        import ssl
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:   # CI and the fake servers (plain HTTP) don't need it
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
    import io
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


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


def audio_pcm(data, rate_hint=SR, service=None):
    """16-bit mono PCM at 24 kHz from whatever a service sent: WAV, else (MP3 and the like) through
    ffmpeg, else raw PCM at rate_hint. A text answer (JSON, HTML) is refused, never cached as noise."""
    head = data[:64].lstrip()
    if not data or head[:1] in (b"{", b"[", b"<"):
        raise ServiceError("bad_request", service, "the service answered with text, not audio: "
                           + _message(data)[:200] if data else "the service answered with no audio")
    if data[:4] == b"RIFF":
        pcm, rate = wav_pcm(data)
        return resample(pcm, rate, SR)
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2") or data[:4] in (b"OggS", b"fLaC"):
        import subprocess
        import ffmpeg
        exe = ffmpeg.exe()
        if not exe:
            raise SystemExit("A service sent compressed audio, which needs ffmpeg to read: rerun ./sweatcast setup.")
        out = subprocess.run([exe, "-loglevel", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", str(SR),
                              "pipe:1"], input=data, capture_output=True, check=True)
        return out.stdout
    return resample(data[:len(data) - len(data) % 2], rate_hint, SR)


def rate(service, model):
    """US dollars per million billed units (characters, or bytes for Fish), approximate."""
    rates = services()[service]["usd_per_million"]
    if isinstance(rates, dict):
        return rates.get(model) or next(iter(rates.values()))
    return rates


def estimate(service, model, texts):
    """(characters, approximate US dollars) for sending `texts`."""
    s = services()[service]
    chars = sum(len(t) for t in texts)
    units = sum(len(t.encode("utf-8")) for t in texts) if s.get("unit") == "bytes" else chars
    return chars, units * rate(service, model) / 1e6


def voice_for(p, route=None, pending=False):
    """The voice dict for web coach `p`: its saved voice on its own service (`route` is ignored; a web coach
    speaks only through the service that made it). No key in it, and no clip: the service holds the voice.
    With `pending`, a coach still to be made (no voice yet) gets a voice dict with no voice ID, for the
    lint's and the brief's estimated pace only; nothing renders from it."""
    import personas
    if not p.is_web:
        raise SystemExit(f"{p.name} is a local coach: a local coach renders only locally.")
    service = p.service
    if service not in services():
        raise SystemExit(f"{p.name} names no known web service ({service or 'none'}); "
                         f"the services: {', '.join(services())}.")
    if not p.voice_id and not (pending and p.pending):
        raise SystemExit(f"{p.name} has no voice yet" + (f" ({p.pending} pending)" if p.pending else "")
                         + ": audition one and keep it (the coach skill).")
    s = services()[service]
    model = p.model or s["default_model"]
    return {"name": p.name, "persona": p.slug, "persona_dir": p.folder, "engine": service, "backend": "cloud",
            "route": service, "service": service, "model": model, "voice_id": p.voice_id, "style": p.style,
            "revision": None, "generate": {}, "pace_file": p.pace_file,
            "concurrency": int(s.get("concurrency") or 1), "max_chars": int(s.get("max_chars") or 0),
            "key": personas.web_key(p, model)}


def speaker(voice):
    """say(text, seed, previous_text=None, next_text=None) for the voice's service."""
    module = importlib.import_module(f"services.{voice['service']}")
    return module.speaker(voice)


def key_or_stop(service):
    import keys
    value = keys.get(service)
    if not value:
        raise ServiceError("auth", service, f"no key on this computer: ./sweatcast keys init {service}, then paste "
                                            f"the key into me/.env after {keys.SERVICE_VARS[service]}=")
    return value


def multipart(fields, files):
    """(body, content type) for a multipart/form-data upload: `fields` {name: text}, `files`
    [(field, filename, bytes, content type)]."""
    import uuid
    boundary = "sweatcast-" + uuid.uuid4().hex
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
