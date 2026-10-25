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
