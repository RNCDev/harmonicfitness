"""Local stand-ins for the cloud voice services: a threaded HTTP server on 127.0.0.1 that records each
request and answers it from a function the test sets. No network leaves the machine."""
import http.server
import io
import math
import struct
import threading
import wave


def tone_wav(seconds=0.5, rate=24000, bogus_size=False, channels=1):
    """A WAV of a quiet 220 Hz tone. bogus_size writes Fish's placeholder RIFF and data sizes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * 220 * i / rate))) * channels
                          for i in range(int(seconds * rate)))
        w.writeframes(frames)
    data = bytearray(buf.getvalue())
    if bogus_size:
        data[4:8] = struct.pack("<I", 4294967076)
        at = data.find(b"data")
        data[at + 4:at + 8] = struct.pack("<I", 4294967040)
    return bytes(data)


def tone_pcm(seconds=0.5, rate=24000):
    return b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * 220 * i / rate)))
                    for i in range(int(seconds * rate)))


class Request:
    def __init__(self, method, path, headers, body):
        self.method, self.path, self.headers, self.body = method, path, headers, body


class FakeService:
    """Start with `with FakeService(answer) as fake:`; fake.url is the base URL, fake.requests what came in.
    answer(request) returns (status, headers dict, body bytes)."""

    def __init__(self, answer):
        self.answer = answer
        self.requests = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _serve(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                req = Request(self.command, self.path, {k.lower(): v for k, v in self.headers.items()}, body)
                outer.requests.append(req)
                status, headers, data = outer.answer(req)
                self.send_response(status)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_POST = do_GET = do_DELETE = _serve

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self):
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def _b64(data):
    import base64
    return base64.b64encode(data).decode()


def design_answer(service):
    """An answer for one web service that designs, saves, speaks and deletes as its documented API does:
    Fish two candidates (44.1 kHz WAVs with signatures), ElevenLabs three previews, Gemini one stored
    voice (and its speech), Inworld two previews."""
    import itertools
    import json
    count = itertools.count(1)

    def answer(req):
        ok = lambda body: (200, {"Content-Type": "application/json"}, json.dumps(body).encode())
        if req.method == "DELETE":
            return 204, {}, b""
        if service == "fish":
            if req.path == "/v1/voice-design":
                return ok({"candidates": [{"id": f"cand-{i}", "audio_base64": _b64(tone_wav(1.0 - 0.2 * i, rate=44100)),
                                           "sample_rate": 44100, "text": "Okay, set your feet.",
                                           "signature": f"sig-{i}"} for i in range(2)]})
            if req.path == "/model":
                return 201, {"Content-Type": "application/json"}, json.dumps({"_id": "fish-model-1",
                                                                              "state": "trained"}).encode()
        if service == "elevenlabs":
            if req.path.startswith("/v1/text-to-voice/design"):
                return ok({"previews": [{"audio_base_64": _b64(tone_pcm(1.0)), "generated_voice_id": f"g{i}"}
                                        for i in range(3)], "text": "the words spoken"})
            if req.path == "/v1/text-to-voice":
                return ok({"voice_id": "el-saved-5"})
        if service == "gemini":
            if req.path == "/v1beta/voices":
                return ok({"id": f"gem-voice-{next(count)}",
                           "sample_audio": {"mime_type": "audio/wav", "data": _b64(tone_wav(2.0))}})
            if req.path == "/v1beta/interactions":
                return ok({"steps": [{"content": [{"type": "audio", "mime_type": "audio/wav",
                                                   "data": _b64(tone_wav(1.0))}]}]})
        if service == "inworld":
            if req.path == "/voices/v1/voices:design":
                return ok({"previewVoices": [{"voiceId": f"ws__design-{i}", "previewText": "Okay, set.",
                                              "previewAudio": _b64(tone_wav(0.9))} for i in range(2)]})
            if req.path.endswith(":publish"):
                return ok({"voiceId": req.path.split("/")[-1].split(":")[0]})
        return 404, {}, b'{"message": "not found"}'
    return answer

