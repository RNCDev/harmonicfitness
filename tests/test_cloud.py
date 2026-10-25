"""Cloud voices against local fake servers that mimic each service's documented API.
No network leaves the machine, and every key is a made-up test value."""
import base64
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("SWEATCAST_BACKEND", "mlx")

import cli  # noqa: E402
import cloud  # noqa: E402
import personas  # noqa: E402
from fakes import FakeService, tone_pcm, tone_wav  # noqa: E402
from test_personas import FIXTURE, persona_home  # noqa: E402

SECRET = "sk-test-NEVERPRINT-123"
DRAFT = os.path.join(ROOT, "tests", "fixtures", "example.draft.txt")


def wav_answer(req):
    return 200, {"Content-Type": "audio/wav"}, tone_wav(0.4, rate=44100, bogus_size=True)


class Core(unittest.TestCase):
    def test_wav_with_a_bogus_size_reads_to_the_end(self):
        pcm, rate = cloud.wav_pcm(tone_wav(0.5, rate=24000, bogus_size=True))
        self.assertEqual(rate, 24000)
        self.assertEqual(len(pcm), 2 * 12000)
        stereo, _ = cloud.wav_pcm(tone_wav(0.5, channels=2))
        self.assertEqual(len(stereo), 2 * 12000)   # mixed down to mono

    def test_resample_44100_to_24000_keeps_length(self):
        pcm = tone_pcm(1.0, rate=44100)
        out = cloud.resample(pcm, 44100, 24000)
        self.assertAlmostEqual(len(out) / 2, 24000, delta=2)
        self.assertEqual(cloud.resample(pcm, 24000, 24000), pcm)

    def test_trim_matches_the_local_rule(self):
        pcm = b"\x00\x00" * 2400 + tone_pcm(0.2) + b"\x00\x00" * 4800
        out = cloud.trim(pcm)
        self.assertLess(len(out), len(pcm))
        self.assertGreater(len(out), len(tone_pcm(0.2)))

    def test_429_then_success_is_retried(self):
        calls = []

        def answer(req):
            calls.append(1)
            return (429, {}, b"{}") if len(calls) < 3 else (200, {}, b"ok")
        with FakeService(answer) as fake:
            status, _, data = cloud.request("POST", fake.url + "/x", {}, b"", sleep=lambda s: None)
        self.assertEqual((status, data, len(calls)), (200, b"ok", 3))

    def test_a_request_that_saves_is_retried_only_on_429(self):
        calls = []

        def answer(req):
            calls.append(1)
            return (500, {}, b"{}")
        with FakeService(answer) as fake:
            with self.assertRaises(cloud.ServiceError):
                cloud.request("POST", fake.url + "/x", {}, b"", sleep=lambda s: None, idempotent=False)
        self.assertEqual(len(calls), 1)   # the service may have saved it: never a second voice
        calls.clear()

        def limited(req):
            calls.append(1)
            return (429, {}, b"{}") if len(calls) < 2 else (201, {}, b"ok")
        with FakeService(limited) as fake:
            status, _, data = cloud.request("POST", fake.url + "/x", {}, b"", sleep=lambda s: None, idempotent=False)
        self.assertEqual((status, data, len(calls)), (201, b"ok", 2))

    def test_a_request_that_saves_retries_a_refused_connection_not_a_timeout(self):
        import socket
        import urllib.error
        tries = []

        def refused(*a, **k):
            tries.append(1)
            raise urllib.error.URLError(ConnectionRefusedError(61, "refused"))
        with mock.patch("urllib.request.urlopen", refused), self.assertRaises(cloud.ServiceError):
            cloud.request("POST", "http://127.0.0.1:9/x", {}, b"", sleep=lambda s: None, idempotent=False, tries=3)
        self.assertEqual(len(tries), 3)   # nothing was sent: safe to try again
        tries.clear()

        def timed_out(*a, **k):
            tries.append(1)
            raise socket.timeout("timed out")
        with mock.patch("urllib.request.urlopen", timed_out), self.assertRaises(cloud.ServiceError):
            cloud.request("POST", "http://127.0.0.1:9/x", {}, b"", sleep=lambda s: None, idempotent=False, tries=3)
        self.assertEqual(len(tries), 1)

    def test_a_cut_off_answer_is_retried_only_when_safe(self):
        import http.client
        tries = []

        def cut_off(*a, **k):
            tries.append(1)
            raise http.client.IncompleteRead(b"RIFF")
        with mock.patch("urllib.request.urlopen", cut_off), self.assertRaises(cloud.ServiceError) as got:
            cloud.request("POST", "http://127.0.0.1:9/x", {}, b"", sleep=lambda s: None, tries=3)
        self.assertEqual((len(tries), got.exception.kind), (3, "unavailable"))
        tries.clear()
        with mock.patch("urllib.request.urlopen", cut_off), self.assertRaises(cloud.ServiceError):
            cloud.request("POST", "http://127.0.0.1:9/x", {}, b"", sleep=lambda s: None, tries=3, idempotent=False)
        self.assertEqual(len(tries), 1)   # a save may have landed: never sent twice

    def test_a_stopping_render_ends_retries_at_once(self):
        import threading
        stop = threading.Event()

        def answer(req):
            stop.set()   # the render fails elsewhere while this request is out
            return 503, {}, b"{}"
        cloud.stop_on(stop)
        self.addCleanup(cloud.stop_on, None)
        with FakeService(answer) as fake, mock.patch.dict(os.environ, {"SWEATCAST_RETRY_WAIT": "1"}):
            with self.assertRaises(cloud.ServiceError):
                cloud.request("POST", fake.url + "/x", {}, b"", service="fish")   # no backoff slept through
        self.assertEqual(len(fake.requests), 1)

    def test_an_unreadable_2xx_answer_is_a_service_error(self):
        for body in (b"<html>oops</html>", b"[1, 2]", b"", b"\xff\xfe"):
            with self.assertRaises(cloud.ServiceError) as got:
                cloud.json_answer(body, "fish")
            self.assertEqual(got.exception.kind, "bad_request")
        self.assertEqual(cloud.json_answer(b'{"a": 1}', "fish"), {"a": 1})
        with self.assertRaises(cloud.ServiceError):
            cloud.b64_audio("not base64!", "fish")

    def test_a_brought_clip_that_isnt_wav_never_becomes_raw_pcm(self):
        import coaches
        m4a = b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00M4A mp42isom" + bytes(2000)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "clip.m4a")
            with open(path, "wb") as f:
                f.write(m4a)
            with mock.patch.object(cloud, "ffmpeg_pcm", return_value=tone_pcm(0.2)) as conv:
                data = coaches._clip_bytes(path)
            conv.assert_called_once()
            self.assertEqual(cloud.wav_pcm(data), (tone_pcm(0.2), 24000))
            with mock.patch("ffmpeg.exe", return_value=None), self.assertRaises(SystemExit) as got:
                coaches._clip_bytes(path)
            self.assertIn("ffmpeg", str(got.exception.code))
            wav = os.path.join(d, "clip.wav")
            with open(wav, "wb") as f:
                f.write(tone_wav(0.3, rate=44100))
            with mock.patch.object(cloud, "ffmpeg_pcm", side_effect=AssertionError("a WAV needs no ffmpeg")):
                pcm, rate = cloud.wav_pcm(coaches._clip_bytes(wav))
            self.assertEqual(rate, 24000)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_ffmpeg_refusing_a_clip_is_a_message(self):
        with self.assertRaises(SystemExit) as got:
            cloud.ffmpeg_pcm(b"\x00\x00\x00\x20ftypM4A " + bytes(64), "The clip")
        self.assertIn("The clip", str(got.exception.code))

    def test_errors_by_kind(self):
        for status, body, kind in ((401, b'{"message": "Invalid api key"}', "auth"),
                                   (402, b'{"status": 402, "message": "No payment"}', "billing"),
                                   (400, b'{"detail": {"message": "text too long"}}', "bad_request"),
                                   (400, b'{"error_code": "quota_exceeded", "message": "out"}', "quota"),
                                   (503, b"{}", "unavailable")):
            with FakeService(lambda req, s=status, b=body: (s, {}, b)) as fake:
                with self.assertRaises(cloud.ServiceError) as e:
                    cloud.request("POST", fake.url + "/x", {"Authorization": f"Bearer {SECRET}"}, b"",
                                  service="fish", sleep=lambda s: None)
            self.assertEqual(e.exception.kind, kind, status)
            self.assertNotIn(SECRET, str(e.exception))

    def test_estimate_counts_bytes_for_fish_and_characters_elsewhere(self):
        chars, usd = cloud.estimate("fish", "s2.1-pro", ["Zoë"] * 1000)
        self.assertEqual(chars, 3000)
        self.assertAlmostEqual(usd, 4000 * 15 / 1e6)
        _, usd = cloud.estimate("inworld", "inworld-tts-2", ["abc"] * 1000)
        self.assertAlmostEqual(usd, 3000 * 25 / 1e6)
        _, usd = cloud.estimate("gemini", "gemini-3.8-flash-tts", ["abc"] * 1000)
        self.assertAlmostEqual(usd, 3000 * 13.5 / 1e6)

    def test_services_settings(self):
        s = cloud.services()
        self.assertEqual(set(s), {"fish", "elevenlabs", "gemini", "inworld"})
        for name in s:
            self.assertTrue(s[name]["tried_live"], name)
            self.assertEqual(s[name]["rates_checked"], "2026-10-25")
            for gone in ("copies_clip", "designs", "stock_voices"):
                self.assertNotIn(gone, s[name])
        self.assertEqual(s["fish"]["default_model"], "s2.1-pro")
        self.assertEqual(s["fish"]["design_usd"], 0.01)
        self.assertEqual(s["elevenlabs"]["default_model"], "eleven_v4")
        self.assertIn("Free", s["elevenlabs"]["note"])
        self.assertEqual((s["gemini"]["default_model"], s["gemini"]["url"]),
                         ("gemini-3.8-flash-tts", "https://generativelanguage.googleapis.com"))
        self.assertEqual((s["inworld"]["default_model"], s["inworld"]["url"]),
                         ("inworld-tts-2", "https://api.inworld.ai"))
        self.assertEqual({n: (s[n]["concurrency"], s[n]["max_chars"]) for n in s},
                         {"fish": (5, 0), "elevenlabs": (2, 10000), "gemini": (2, 0), "inworld": (5, 2000)})
        self.assertEqual(cloud.rate("gemini", "gemini-3.8-flash-tts"), 13.5)
        self.assertEqual(cloud.rate("gemini", "gemini-3.8-flash-lite-tts"), 9)
        self.assertEqual(cloud.rate("inworld", "inworld-tts-2-flash"), 15)
        self.assertEqual(cloud.rate("elevenlabs", "eleven_v4_turbo"), 40)
        for n in ("gemini", "inworld"):
            self.assertEqual(s[n]["unit"], "characters")
        self.assertEqual(s["gemini"]["design_usd"], 0.01)   # spec decision 2
        self.assertNotIn("design_usd", s["inworld"])


VOICE_IDS = {"fish": "fish-model-1", "elevenlabs": "el-voice-1", "gemini": "gemini-voice-1",
             "inworld": "workspace__design-voice-1"}
COACHES = {"fish": "Coach Reed", "elevenlabs": "Coach Ellis", "gemini": "Coach Nolan", "inworld": "Coach Owen"}


def web_coach(folder, service, name=None, **extra):
    """A schema-5 web coach on `service` with a saved voice ID, in personas folder `folder`."""
    import context
    name = name or COACHES[service]
    settings = dict({"name": name, "kind": "web", "service": service, "voice_id": VOICE_IDS[service]}, **extra)
    path = os.path.join(folder, f"{personas.slug(name)}-{service}")   # as the template and keep name it
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "persona.md"), "w", encoding="utf-8") as f:
        f.write(context.persona_text(settings, "## How this coach talks\n"))
    return name


def b64(data):
    return base64.b64encode(data).decode()


def gemini_audio_answer(wav=None):
    """An interactions answer with the audio two levels down, as the live probe found it."""
    audio = {"type": "audio", "mime_type": "audio/wav", "data": b64(wav or tone_wav(0.4, rate=24000))}
    return json.dumps({"id": "int-1", "status": "completed", "usage": {"total_tokens": 9},
                       "steps": [{"type": "thought"}, {"type": "model_output", "content": [audio]}]}).encode()


def every_service_answer(req):
    """Speech on any of the four services, by path."""
    if req.path == "/v1/tts":
        return wav_answer(req)
    if req.path.startswith("/v1/text-to-speech/"):
        return 200, {"Content-Type": "audio/pcm"}, tone_pcm(0.3)
    if req.path == "/v1beta/interactions":
        return 200, {"Content-Type": "application/json"}, gemini_audio_answer()
    if req.path == "/tts/v1/voice":
        return 200, {"Content-Type": "application/json"}, json.dumps({"audioContent": b64(tone_wav(0.3))}).encode()
    return 404, {}, b'{"message": "not found"}'


class WebVoice(unittest.TestCase):
    """cloud.voice_for: a web coach's voice dict, by its saved voice ID; a local coach never on a web route."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.folder = persona_home(self.d)
        patch = mock.patch.object(personas.paths, "PERSONAS", self.folder)
        patch.start()
        self.addCleanup(patch.stop)

    def test_voice_for_a_web_coach(self):
        web_coach(self.folder, "inworld")
        p = personas.lookup("Coach Owen")
        v = personas.voice_for(p, "fish")   # the route is ignored: a web coach speaks through its service
        self.assertEqual({k: v[k] for k in ("name", "persona", "engine", "backend", "route", "service", "model",
                                            "voice_id", "style", "revision", "generate", "concurrency", "max_chars")},
                         {"name": "Coach Owen", "persona": "coach-owen-inworld", "engine": "inworld", "backend": "cloud",
                          "route": "inworld", "service": "inworld", "model": "inworld-tts-2",
                          "voice_id": VOICE_IDS["inworld"], "style": "", "revision": None, "generate": {},
                          "concurrency": 5, "max_chars": 2000})
        self.assertEqual(v["key"], personas.web_key(p, "inworld-tts-2"))
        self.assertEqual((v["persona_dir"], v["pace_file"]), (p.folder, p.pace_file))
        self.assertNotIn("ref_audio", v)
        self.assertEqual(cloud.voice_for(p, "inworld"), v)

    def test_a_chosen_model_changes_the_key(self):
        web_coach(self.folder, "elevenlabs", model="eleven_v4_turbo")
        p = personas.lookup("Coach Ellis")
        v = personas.voice_for(p, "elevenlabs")
        self.assertEqual(v["model"], "eleven_v4_turbo")
        self.assertEqual(v["key"], personas.web_key(p, "eleven_v4_turbo"))
        self.assertNotEqual(v["key"], personas.web_key(p, "eleven_v4"))

    def test_a_web_coach_with_no_voice_yet_stops(self):
        import context
        path = os.path.join(self.folder, "coach-reed-fish")
        os.makedirs(path)
        with open(os.path.join(path, "persona.md"), "w", encoding="utf-8") as f:
            f.write(context.persona_text({"name": "Coach Reed", "kind": "web", "service": "fish", "placeholder": True,
                                          "pending": "design"}, "## How this coach talks\n"))
        with self.assertRaises(SystemExit) as e:
            personas.voice_for(personas.lookup("Coach Reed"), "fish")
        self.assertIn("Coach Reed", str(e.exception.code))
        self.assertIn("audition", str(e.exception.code))

    def test_a_local_coach_never_renders_on_a_web_route(self):
        with self.assertRaises(SystemExit) as e:
            personas.voice_for(personas.lookup("Coach Test"), "fish")
        self.assertIn("local coach", str(e.exception.code))
        self.assertEqual(personas.voice_for(personas.lookup("Coach Test"), "local")["route"], "local")


class ServiceCase(unittest.TestCase):
    """A web coach and a test key for one service, with the service pointed at a fake."""
    SERVICE = None

    def setUp(self):
        import keys
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.folder = persona_home(self.d)
        web_coach(self.folder, self.SERVICE)
        patches = [mock.patch.object(personas.paths, "PERSONAS", self.folder),
                   mock.patch.dict(os.environ, {keys.SERVICE_VARS[self.SERVICE]: SECRET, "SWEATCAST_RETRY_WAIT": "0"})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    @property
    def module(self):
        import importlib
        return importlib.import_module(f"services.{self.SERVICE}")

    def coach(self):
        return personas.lookup(COACHES[self.SERVICE])

    def voice(self):
        return personas.voice_for(self.coach(), self.SERVICE)

    def serve(self, answer):
        fake = FakeService(answer)
        fake.__enter__()
        self.addCleanup(fake.__exit__)
        patch = mock.patch.dict(os.environ, {f"SWEATCAST_{self.SERVICE.upper()}_URL": fake.url})
        patch.start()
        self.addCleanup(patch.stop)
        return fake

    def check_candidate(self, c, text):
        self.assertEqual(set(c), {"pcm", "wav", "text", "draft_id", "signature"})
        self.assertEqual(c["text"], text)
        self.assertGreater(len(c["pcm"]), 0)
        pcm, rate = cloud.wav_pcm(c["wav"])
        self.assertGreater(len(pcm), 0)

    def check_saved_once(self, call, saved):
        """A request that saves a voice: a 500 isn't retried (the service may have saved it), a 429 is."""
        fake = self.serve(lambda r: (500, {}, b'{"message": "oops"}'))
        with self.assertRaises(cloud.ServiceError):
            call()
        self.assertEqual(len(fake.requests), 1)
        answers = iter([(429, {}, b"{}")])
        fake.answer = lambda r: next(answers, None) or saved(r)
        call()
        path = fake.requests[0].path
        self.assertEqual(len([r for r in fake.requests if r.path == path]), 3)

    def check_delete(self, path, gone_status=200):
        """delete(): True on the service's 2xx, True on a 404 (already gone), an error otherwise."""
        fake = self.serve(lambda r: (gone_status, {}, b"" if gone_status == 204 else b"{}"))
        self.assertTrue(self.module.delete("voice-9"))
        self.assertEqual((fake.requests[0].method, fake.requests[0].path), ("DELETE", path.format(id="voice-9")))
        self.assertNotIn(SECRET, fake.requests[0].path)
        fake.answer = lambda r: (404, {}, b'{"message": "not found"}')
        self.assertTrue(self.module.delete("voice-9"))
        fake.answer = lambda r: (401, {}, b'{"message": "Invalid api key"}')
        with self.assertRaises(cloud.ServiceError) as e:
            self.module.delete("voice-9")
        self.assertEqual(e.exception.kind, "auth")


def fish_design_answer(req):
    candidate = lambda i: {"id": f"cand-{i}", "index": i, "audio_base64": b64(FISH_WAVS[i]), "sample_rate": 44100,
                           "duration_ms": 1000, "text": "Okay, set your feet.", "language": "en",
                           "instruct": "x", "features": {}, "audio_token_sha256": "abc", "signature": f"sig-{i}"}
    return 200, {"Content-Type": "application/json"}, json.dumps({"candidates": [candidate(0), candidate(1)]}).encode()


FISH_WAVS = [tone_wav(1.0, rate=44100), tone_wav(0.8, rate=44100)]


class Fish(ServiceCase):
    SERVICE = "fish"

    def test_fish_speaks_by_reference_id(self):
        fake = self.serve(wav_answer)
        pcm = cloud.speaker(self.voice())("Set your feet.", 42, previous_text="Hi.", next_text="Rest.")
        req = fake.requests[0]
        self.assertEqual((req.method, req.path), ("POST", "/v1/tts"))
        self.assertEqual(req.headers["authorization"], f"Bearer {SECRET}")
        self.assertEqual(req.headers["model"], "s2.1-pro")
        self.assertEqual(req.headers["content-type"], "application/json")
        self.assertEqual(json.loads(req.body), {"text": "Set your feet.", "reference_id": VOICE_IDS["fish"],
                                                "format": "wav", "sample_rate": 24000})
        self.assertAlmostEqual(len(pcm) / 2 / 24000, 0.4, delta=0.05)   # resampled to 24 kHz

    def test_fish_402_is_billing(self):
        self.serve(lambda r: (402, {}, b'{"status": 402, "message": "No payment"}'))
        with self.assertRaises(cloud.ServiceError) as e:
            cloud.speaker(self.voice())("Hi.", 42)
        self.assertEqual(e.exception.kind, "billing")

    def test_fish_design_keeps_signature_and_wav(self):
        fake = self.serve(fish_design_answer)
        out = self.module.design("A warm coach in her forties.", "Okay, set your feet.", 2, "ignored")
        req = fake.requests[0]
        self.assertEqual((req.path, req.headers["model"]), ("/v1/voice-design", "voice-design-1"))
        self.assertEqual(req.headers["authorization"], f"Bearer {SECRET}")
        self.assertEqual(json.loads(req.body), {"instruction": "A warm coach in her forties.",
                                                "reference_text": "Okay, set your feet.", "language": "en", "n": 2})
        self.assertEqual(len(out), 2)
        for i, c in enumerate(out):
            self.check_candidate(c, "Okay, set your feet.")
            self.assertEqual(c["wav"], FISH_WAVS[i])   # exactly the WAV Fish sent: the save sends it back
            self.assertEqual((c["signature"], c["draft_id"]), (f"sig-{i}", f"cand-{i}"))
        self.assertAlmostEqual(len(out[0]["pcm"]) / 2 / 24000, 1.0, delta=0.15)

    def test_fish_save_posts_multipart_private_model(self):
        fake = self.serve(lambda r: (201, {}, json.dumps({"_id": "model-77", "state": "trained",
                                                          "visibility": "private"}).encode()))
        candidate = {"pcm": b"\x00\x01" * 10, "wav": FISH_WAVS[0], "text": "Okay, set your feet.",
                     "draft_id": "cand-0", "signature": "sig-0"}
        voice_id = self.module.save(candidate, "Coach Reed", "A man in his forties.", FISH_WAVS[0])
        self.assertEqual(voice_id, "model-77")
        req = fake.requests[0]
        self.assertEqual((req.method, req.path), ("POST", "/model"))
        self.assertEqual(req.headers["authorization"], f"Bearer {SECRET}")
        self.assertTrue(req.headers["content-type"].startswith("multipart/form-data; boundary="))
        for field, value in (("visibility", "private"), ("type", "tts"), ("title", "sweatcast Coach Reed"),
                             ("train_mode", "fast"), ("texts", "Okay, set your feet."),
                             ("voice_design_signatures", "sig-0")):
            self.assertIn(f'name="{field}"\r\n\r\n{value}\r\n'.encode(), req.body, field)
        self.assertIn(b'name="voices"; filename="voice.wav"\r\nContent-Type: audio/wav\r\n\r\n' + FISH_WAVS[0],
                      req.body)

    def test_fish_save_is_not_retried_after_sending(self):
        c = {"pcm": b"", "wav": FISH_WAVS[0], "text": "x", "draft_id": "d-1", "signature": "sig"}
        self.check_saved_once(lambda: self.module.save(c, "Coach Reed", "A man.", FISH_WAVS[0]),
                              lambda r: (201, {}, b'{"_id": "model-1"}'))

    def test_fish_delete(self):
        self.check_delete("/model/{id}", gone_status=204)


def elevenlabs_answer(req):
    if req.path.startswith("/v1/text-to-speech/"):
        return 200, {"Content-Type": "audio/pcm"}, tone_pcm(0.3)
    if req.path.startswith("/v1/text-to-voice/design"):
        return 200, {}, json.dumps({"previews": [{"audio_base_64": b64(tone_pcm(1.0)), "generated_voice_id": f"g{i}",
                                                  "media_type": "audio/pcm", "duration_secs": 1.0} for i in range(3)],
                                    "text": "the words spoken"}).encode()
    if req.path == "/v1/text-to-voice":
        return 200, {}, json.dumps({"voice_id": "el-saved-5", "name": "x"}).encode()
    return 404, {}, b"{}"


class ElevenLabs(ServiceCase):
    SERVICE = "elevenlabs"

    def test_elevenlabs_sends_neighbors_and_seed(self):
        fake = self.serve(elevenlabs_answer)
        pcm = cloud.speaker(self.voice())("Two more.", 42, previous_text="Set your feet.", next_text="Rest.")
        req = fake.requests[0]
        self.assertEqual(req.path, f"/v1/text-to-speech/{VOICE_IDS['elevenlabs']}?output_format=pcm_24000")
        self.assertEqual(req.headers["xi-api-key"], SECRET)
        self.assertEqual(json.loads(req.body), {"text": "Two more.", "model_id": "eleven_v4", "seed": 42,
                                                "previous_text": "Set your feet.", "next_text": "Rest."})
        self.assertGreater(len(pcm), 0)
        self.assertEqual(len(fake.requests), 1)   # no clone first, ever
        self.assertFalse(any(r.path == "/v1/voices/add" for r in fake.requests))

    def test_elevenlabs_design_returns_three_with_generated_ids(self):
        fake = self.serve(elevenlabs_answer)
        out = self.module.design("A warm coach in her forties.", "Okay, set your feet.", 2, "ignored")
        req = fake.requests[0]
        self.assertEqual(req.path, "/v1/text-to-voice/design?output_format=pcm_24000")
        body = json.loads(req.body)
        self.assertEqual(set(body), {"voice_description", "text"})
        self.assertEqual(body["voice_description"], "A warm coach in her forties.")
        self.assertGreaterEqual(len(body["text"]), 100)
        self.assertTrue(body["text"].startswith("Okay, set your feet."))
        self.assertEqual([c["draft_id"] for c in out], ["g0", "g1", "g2"])   # every preview is a candidate
        for c in out:
            self.check_candidate(c, "the words spoken")
            self.assertIsNone(c["signature"])
        self.assertAlmostEqual(len(cloud.wav_pcm(out[0]["wav"])[0]) / 2 / 24000, len(out[0]["pcm"]) / 2 / 24000,
                               delta=0.01)

    def test_elevenlabs_save_is_not_retried_after_sending(self):
        c = {"pcm": b"", "wav": b"", "text": "x", "draft_id": "g1", "signature": None}
        self.check_saved_once(lambda: self.module.save(c, "Coach Ellis", "A man.", b""),
                              lambda r: (200, {}, b'{"voice_id": "el-1"}'))

    def test_elevenlabs_save_posts_generated_voice_id(self):
        fake = self.serve(elevenlabs_answer)
        candidate = {"pcm": b"\x00\x01", "wav": b"", "text": "x", "draft_id": "g1", "signature": None}
        self.assertEqual(self.module.save(candidate, "Coach Ellis", "D" * 1500, b""), "el-saved-5")
        req = fake.requests[0]
        self.assertEqual((req.method, req.path), ("POST", "/v1/text-to-voice"))
        self.assertEqual(json.loads(req.body), {"voice_name": "sweatcast Coach Ellis", "voice_description": "D" * 1000,
                                                "generated_voice_id": "g1"})

    def test_elevenlabs_delete(self):
        self.check_delete("/v1/voices/{id}")


class Gemini(ServiceCase):
    SERVICE = "gemini"

    def design_answer(self, req):
        if req.path == "/v1beta/voices":
            return 200, {}, json.dumps({"id": "voice-abc", "model": "gemini-3.8-flash-tts", "type": "prompted",
                                        "expire_time": "2026-11-25T00:00:00Z", "display_name": "x",
                                        "prompted": {"input": "x"}, "usage": {},
                                        "sample_audio": {"mime_type": "audio/wav",
                                                         "data": b64(tone_wav(2.0))}}).encode()
        if req.path == "/v1beta/interactions":
            return 200, {}, gemini_audio_answer(tone_wav(1.0))
        return 404, {}, b"{}"

    def test_gemini_design_body_has_only_input_in_prompted(self):
        fake = self.serve(self.design_answer)
        out = self.module.design("A man in his forties.", "Okay, set your feet.", 1, "sweatcast audition a1 C")
        create, speech = fake.requests
        self.assertEqual((create.method, create.path), ("POST", "/v1beta/voices"))
        self.assertEqual(create.headers["x-goog-api-key"], SECRET)
        self.assertEqual(json.loads(create.body), {"voice": {"type": "prompted",
                                                             "display_name": "sweatcast audition a1 C",
                                                             "prompted": {"input": "A man in his forties."}},
                                                   "store": True})
        self.assertEqual(speech.path, "/v1beta/interactions")   # the line, spoken once by the new voice
        body = json.loads(speech.body)
        self.assertEqual(body["generation_config"], {"speech_config": [{"voice": "voice-abc"}]})
        self.assertEqual(body["input"], [{"type": "text", "text": "Okay, set your feet."}])
        self.assertEqual(len(out), 1)
        self.check_candidate(out[0], "Okay, set your feet.")
        self.assertEqual((out[0]["draft_id"], out[0]["signature"]), ("voice-abc", None))
        self.assertAlmostEqual(len(out[0]["pcm"]) / 2 / 24000, 1.0, delta=0.15)   # the line, not sample_audio

    def test_gemini_design_raises_when_its_speech_fails(self):
        def answer(req):
            if req.path == "/v1beta/interactions":
                return 400, {}, b'{"error": {"message": "bad"}}'
            return self.design_answer(req)
        fake = self.serve(answer)
        with self.assertRaises(cloud.ServiceError):
            self.module.design("A man in his forties.", "Okay, set your feet.", 1, "label")
        self.assertEqual([(r.method, r.path) for r in fake.requests if r.method == "DELETE"],
                         [("DELETE", "/v1beta/voices/voice-abc")])   # the stored voice isn't left behind

    def test_gemini_design_raises_the_speech_error_even_if_the_delete_fails(self):
        def answer(req):
            if req.path == "/v1beta/interactions":
                return 400, {}, b'{"error": {"message": "bad speech"}}'
            if req.method == "DELETE":
                return 500, {}, b'{"error": {"message": "delete broke"}}'
            return self.design_answer(req)
        self.serve(answer)
        with self.assertRaises(cloud.ServiceError) as e:
            self.module.design("A man in his forties.", "Okay, set your feet.", 1, "label")
        self.assertIn("bad speech", str(e.exception))

    def test_gemini_speech_finds_audio_anywhere_in_the_answer(self):
        fake = self.serve(lambda r: (200, {}, gemini_audio_answer(tone_wav(0.5, rate=44100))))
        pcm = cloud.speaker(self.voice())("Set your feet.", 42, previous_text="Hi.", next_text="Rest.")
        self.assertAlmostEqual(len(pcm) / 2 / 24000, 0.5, delta=0.05)
        req = fake.requests[0]
        self.assertEqual((req.path, req.headers["x-goog-api-key"]), ("/v1beta/interactions", SECRET))
        self.assertEqual(json.loads(req.body), {"model": "gemini-3.8-flash-tts",
                                                "input": [{"type": "text", "text": "Set your feet."}],
                                                "response_modalities": ["audio"],
                                                "generation_config": {"speech_config": [{"voice": VOICE_IDS["gemini"]}]}})

    def test_gemini_answer_with_no_audio_is_refused(self):
        self.serve(lambda r: (200, {}, b'{"steps": [{"content": [{"type": "text", "text": "no"}]}]}'))
        with self.assertRaises(cloud.ServiceError) as e:
            cloud.speaker(self.voice())("Hi.", 42)
        self.assertEqual(e.exception.kind, "bad_request")

    def test_gemini_text_is_sent_verbatim(self):
        web_coach(self.folder, "gemini", name="Coach Styled", style="Speak like a calm trainer")
        fake = self.serve(lambda r: (200, {}, gemini_audio_answer()))
        cloud.speaker(personas.voice_for(personas.lookup("Coach Styled"), "gemini"))("Two more. Breathe.", 1)
        body = json.loads(fake.requests[0].body)
        self.assertEqual(body["input"], [{"type": "text", "text": "Two more. Breathe."}])
        self.assertNotIn("speech_metadata", fake.requests[0].body.decode())
        self.assertNotIn("calm trainer", fake.requests[0].body.decode())

    def test_gemini_save_is_the_stored_draft(self):
        fake = self.serve(self.design_answer)
        candidate = {"pcm": b"", "wav": b"", "text": "x", "draft_id": "voice-abc", "signature": None}
        self.assertEqual(self.module.save(candidate, "Coach Nolan", "A man.", b""), "voice-abc")
        self.assertEqual(fake.requests, [])   # stored at design time

    def test_gemini_design_is_not_retried_after_sending(self):
        self.check_saved_once(lambda: self.module.design("A man.", "Okay.", 1, "label"),
                              self.design_answer)

    def test_gemini_delete(self):
        self.check_delete("/v1beta/voices/{id}")


INWORLD_WAVS = [tone_wav(0.9), tone_wav(0.7)]


def inworld_answer(req):
    if req.path == "/voices/v1/voices:design":
        return 200, {}, json.dumps({"previewVoices": [{"voiceId": f"ws__design-{i}", "previewText": "Okay, set.",
                                                       "previewAudio": b64(INWORLD_WAVS[i])} for i in range(2)]}).encode()
    if req.path.endswith(":publish"):
        return 200, {}, json.dumps({"voiceId": req.path.split("/")[-1].split(":")[0], "displayName": "x"}).encode()
    if req.path == "/tts/v1/voice":
        return 200, {}, json.dumps({"audioContent": b64(tone_wav(0.3)), "usage": {}}).encode()
    return 404, {}, b"{}"


class Inworld(ServiceCase):
    SERVICE = "inworld"

    def test_inworld_basic_auth_as_given(self):
        fake = self.serve(inworld_answer)
        cloud.speaker(self.voice())("Hi.", 1)
        self.module.design("A man.", "Okay.", 2, "label")
        self.assertTrue(all(r.headers["authorization"] == f"Basic {SECRET}" for r in fake.requests))

    def test_inworld_design_then_publish(self):
        fake = self.serve(inworld_answer)
        out = self.module.design("A man in his forties.", "Okay, set your feet.", 2, "ignored")
        self.assertEqual(json.loads(fake.requests[0].body), {"designPrompt": "A man in his forties.",
                                                             "previewText": "Okay, set your feet.",
                                                             "languageCode": "EN_US", "numberOfSamples": 2})
        self.assertEqual([c["draft_id"] for c in out], ["ws__design-0", "ws__design-1"])
        for i, c in enumerate(out):
            self.check_candidate(c, "Okay, set.")
            self.assertEqual(c["wav"], INWORLD_WAVS[i])
        voice_id = self.module.save(out[1], "Coach Owen", "A man in his forties.", out[1]["wav"])
        self.assertEqual(voice_id, "ws__design-1")
        publish = fake.requests[-1]
        self.assertEqual((publish.method, publish.path), ("POST", "/voices/v1/voices/ws__design-1:publish"))
        self.assertEqual(json.loads(publish.body), {"displayName": "sweatcast Coach Owen",
                                                    "description": "A man in his forties.", "tags": ["sweatcast"]})

    def test_inworld_publish_is_not_retried_after_sending(self):
        c = {"pcm": b"", "wav": FISH_WAVS[0], "text": "x", "draft_id": "d-1", "signature": "sig"}
        self.check_saved_once(lambda: self.module.save(c, "Coach Owen", "A man.", b""),
                              lambda r: (200, {}, b"{}"))

    def test_inworld_publish_without_an_id_keeps_the_draft_id(self):
        self.serve(lambda r: (200, {}, b"{}"))
        candidate = {"pcm": b"", "wav": b"", "text": "x", "draft_id": "ws__design-3", "signature": None}
        self.assertEqual(self.module.save(candidate, "Coach Owen", "A man.", b""), "ws__design-3")

    def test_inworld_design_waits_through_429(self):
        calls = []

        def answer(req):
            calls.append(1)
            if len(calls) == 1:   # a Google-style rate limit: "quota" in the body, a short Retry-After
                return 429, {"Retry-After": "1"}, b'{"code": 8, "message": "RESOURCE_EXHAUSTED: Quota exceeded"}'
            return inworld_answer(req)
        self.serve(answer)
        self.assertEqual(len(self.module.design("A man.", "Okay.", 2, "label")), 2)
        self.assertEqual(len(calls), 2)

    def test_a_429_with_a_long_wait_is_quota(self):
        self.serve(lambda r: (429, {"Retry-After": "86400"}, b'{"message": "Quota exceeded for the month"}'))
        with self.assertRaises(cloud.ServiceError) as e:
            self.module.design("A man.", "Okay.", 2, "label")
        self.assertEqual(e.exception.kind, "quota")

    def test_inworld_linear16_24k(self):
        fake = self.serve(inworld_answer)
        say = cloud.speaker(self.voice())
        pcm = say("Two more.", 42, previous_text="Set your feet.", next_text="Rest.")
        say("First.", 42)
        first, second = (json.loads(r.body) for r in fake.requests)
        self.assertEqual(fake.requests[0].path, "/tts/v1/voice")
        self.assertEqual(first, {"text": "Two more.", "voiceId": VOICE_IDS["inworld"], "modelId": "inworld-tts-2",
                                 "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000},
                                 "synthesisContext": {"previousRequests": [{"text": "Set your feet."}]}})
        self.assertNotIn("synthesisContext", second)
        self.assertAlmostEqual(len(pcm) / 2 / 24000, 0.3, delta=0.05)

    def test_inworld_refuses_a_paragraph_over_2000_characters(self):
        fake = self.serve(inworld_answer)
        with self.assertRaises(cloud.ServiceError) as e:
            cloud.speaker(self.voice())("word " * 401, 42)
        self.assertEqual(e.exception.kind, "bad_request")
        self.assertIn("2000", str(e.exception))
        self.assertEqual(fake.requests, [])

    def test_inworld_delete(self):
        self.check_delete("/voices/v1/voices/{id}")


class UnreadableAnswers(unittest.TestCase):
    """A 2xx answer that isn't the JSON a service documents stops as a ServiceError, never a traceback."""

    def setUp(self):
        import keys
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        env = {var: SECRET for var in keys.SERVICE_VARS.values()}
        env["SWEATCAST_RETRY_WAIT"] = "0"
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)

    def serve(self, body):
        fake = FakeService(lambda r: (200, {"Content-Type": "application/json"}, body))
        fake.__enter__()
        self.addCleanup(fake.__exit__)
        for service in ("fish", "elevenlabs", "gemini", "inworld"):
            patch = mock.patch.dict(os.environ, {f"SWEATCAST_{service.upper()}_URL": fake.url})
            patch.start()
            self.addCleanup(patch.stop)

    def test_every_design_save_and_speech_refuses_a_bad_body(self):
        import importlib
        candidate = {"wav": tone_wav(0.2), "text": "Hi.", "draft_id": "d1", "signature": "s"}
        voice = {"voice_id": "v1", "model": "m", "max_chars": 2000}
        for body in (b"<html>gateway</html>", b'["not", "an object"]', b'{"previewVoices": [{"previewAudio": "@@"}]}'):
            self.serve(body)
            for service in ("fish", "elevenlabs", "gemini", "inworld"):
                module = importlib.import_module(f"services.{service}")
                calls = [lambda: module.design("a coach", "Set your feet.", 1, "label")]
                if service in ("fish", "elevenlabs"):
                    calls.append(lambda: module.save(candidate, "Coach Maya", "a coach"))
                if service == "inworld":
                    calls.append(lambda: module.speaker(voice)("Hello.", 1))
                for call in calls:
                    with self.subTest(service=service, body=body):
                        try:
                            call()
                        except cloud.ServiceError as e:
                            self.assertNotIn(SECRET, str(e))
                        else:
                            self.fail("a bad answer was accepted")

    def test_a_saves_unreadable_answer_says_the_voice_may_be_there(self):
        self.serve(b"<html>oops</html>")
        from services import fish
        with self.assertRaises(cloud.ServiceError) as got:
            fish.save({"wav": tone_wav(0.2), "text": "Hi.", "signature": "s"}, "Coach Maya")
        self.assertIn("sweatcast Coach Maya", str(got.exception))


class CloudRender(unittest.TestCase):
    """tools/render.py with a web coach, end to end against fake services."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.home = os.path.join(self.d, "me")
        shutil.copytree(os.path.join(ROOT, "me.example"), self.home)
        folder = persona_home(self.home)
        for service in COACHES:
            web_coach(folder, service)

    def render_on(self, service, url, *extra):
        import keys
        e = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
        e.update({"SWEATCAST_HOME": self.home, f"SWEATCAST_{service.upper()}_URL": url,
                  keys.SERVICE_VARS[service]: SECRET, "SWEATCAST_RETRY_WAIT": "0"})
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import helpers
        draft_path = helpers.draft_with_menu(DRAFT, os.path.join(self.d, "cloud.draft.txt"), self.home)
        return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "render.py"), draft_path,
                               "--coach", COACHES[service], *extra], env=e, capture_output=True, text=True, timeout=120)

    def render(self, url, *extra):
        return self.render_on("fish", url, *extra)

    def test_a_refused_speech_exits_4(self):
        with FakeService(lambda r: (401, {}, b'{"detail": {"message": "Invalid API key"}}')) as fake:
            out = self.render_on("elevenlabs", fake.url, "--out", os.path.join(self.d, "x.mp3"))
        self.assertEqual(out.returncode, cli.SERVICE, out.stdout + out.stderr)
        self.assertIn("ElevenLabs", out.stdout)
        self.assertNotIn("Traceback", out.stdout + out.stderr)
        self.assertFalse(any(r.path == "/v1/voices/add" for r in fake.requests))

    def test_a_broken_answer_stops_sending_and_caches_nothing(self):
        with FakeService(lambda r: (200, {"Content-Type": "application/json"}, b'{"status": "queued"}')) as fake:
            out = self.render(fake.url, "--out", os.path.join(self.d, "x.mp3"))
        self.assertEqual(out.returncode, cli.ISSUES, out.stdout + out.stderr)
        self.assertLessEqual(len(fake.requests), 6)   # the queued paragraphs were never sent
        self.assertEqual(glob.glob(os.path.join(self.home, "workouts", ".audio-cache", "*.pcm")), [])

    def set_ceiling(self, n):
        prof = os.path.join(self.home, "profile.md")
        with open(prof, encoding="utf-8") as f:
            text = f.read()
        with open(prof, "w", encoding="utf-8") as f:
            f.write(text.replace("+++\n", f"+++\ncloud_max_chars = {n}\n", 1))

    def test_401_raises_auth_and_render_exits_4(self):
        with FakeService(lambda r: (401, {}, b'{"message": "Invalid api key"}')) as fake:
            out = self.render(fake.url, "--out", os.path.join(self.d, "x.mp3"))
        self.assertEqual(out.returncode, cli.SERVICE, out.stdout + out.stderr)
        self.assertIn("Fish Audio", out.stdout + out.stderr)
        self.assertIn("./sweatcast keys", out.stdout + out.stderr)

    def test_ceiling_stops_before_sending(self):
        self.set_ceiling(10)
        with FakeService(wav_answer) as fake:
            out = self.render(fake.url, "--out", os.path.join(self.d, "x.mp3"))
        self.assertEqual(out.returncode, cli.ISSUES, out.stdout + out.stderr)
        self.assertEqual(fake.requests, [])
        self.assertIn("cloud_max_chars", out.stdout)

    def test_follow_is_refused_on_a_cloud_route(self):
        with FakeService(wav_answer) as fake:
            for flag in ("--follow", "--clips-only"):
                out = self.render(fake.url, flag)
                self.assertEqual(out.returncode, cli.USAGE, flag)
                self.assertIn("billed", out.stdout + out.stderr)
            self.assertEqual(fake.requests, [])

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_key_never_reaches_records_logs_or_cache_keys(self):
        import render
        for service in ("fish", "elevenlabs", "gemini", "inworld"):
            with self.subTest(service=service):
                mp3 = os.path.join(self.d, f"{service}.mp3")
                with FakeService(every_service_answer) as fake:
                    out = self.render_on(service, fake.url, "--out", mp3, "--tolerance", "0.5")
                self.assertIn(out.returncode, (0, cli.DRIFT), out.stdout + out.stderr)
                self.assertIn("Sending", out.stdout)
                self.assertTrue(fake.requests)
                self.assertFalse(any(SECRET in r.path or SECRET.encode() in r.body for r in fake.requests))
                texts = [out.stdout, out.stderr]
                for path in glob.glob(os.path.join(self.d, "*.build.json")) + \
                        glob.glob(os.path.join(self.home, "workouts", ".logs", "*")) + \
                        glob.glob(os.path.join(self.home, "personas", "*", "*.json")):
                    with open(path, encoding="utf-8") as f:
                        texts.append(f.read())
                self.assertFalse(any(SECRET in t for t in texts))
                with open(os.path.splitext(mp3)[0] + ".build.json") as f:
                    record = json.load(f)
                self.assertEqual(record["route"], service)
                self.assertGreater(record["chars_sent"], 100)
                self.assertIn("usd_estimate", record)
                import keys
                var = keys.SERVICE_VARS[service]
                with mock.patch.object(personas.paths, "PERSONAS", os.path.join(self.home, "personas")), \
                        mock.patch.object(personas.paths, "PROFILE", os.path.join(self.home, "profile.md")), \
                        mock.patch.object(personas.paths, "ENV_FILE", os.path.join(self.home, ".env")), \
                        mock.patch.dict(os.environ, {var: SECRET}), \
                        mock.patch.object(render, "check_pace_file"):
                    a = render.prepare_voice(personas.resolve(COACHES[service], None))[1]("Hello.")
                    with mock.patch.dict(os.environ, {var: "another-key"}):
                        b = render.prepare_voice(personas.resolve(COACHES[service], None))[1]("Hello.")
                self.assertEqual(a, b)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_web_render_sends_voice_id_and_caches_by_web_key(self):
        mp3 = os.path.join(self.d, "x.mp3")
        with FakeService(wav_answer) as fake:
            first = self.render(fake.url, "--out", mp3, "--tolerance", "0.5")
            self.assertIn(first.returncode, (0, cli.DRIFT), first.stdout + first.stderr)
            sent = [r for r in fake.requests if r.path == "/v1/tts"]
            self.assertGreaterEqual(len(sent), 2)
            self.assertTrue(all(json.loads(r.body)["reference_id"] == VOICE_IDS["fish"] for r in sent))
            self.assertFalse(any(r.path == "/model" for r in fake.requests))   # no clip uploaded: a saved voice
            before = len(fake.requests)
            second = self.render(fake.url, "--out", mp3, "--tolerance", "0.5")
            self.assertIn(second.returncode, (0, cli.DRIFT), second.stdout + second.stderr)
            self.assertEqual(len(fake.requests), before)   # everything came from the cache
        self.assertNotIn("Sending", second.stdout)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_cost_print_for_gemini(self):
        with FakeService(every_service_answer) as fake:
            out = self.render_on("gemini", fake.url, "--out", os.path.join(self.d, "g.mp3"), "--tolerance", "0.5")
        self.assertIn(out.returncode, (0, cli.DRIFT), out.stdout + out.stderr)
        line = next(l for l in out.stdout.splitlines() if l.startswith("Sending"))
        chars = int(line.split()[1].replace(",", ""))
        self.assertEqual(cloud.rate("gemini", "gemini-3.8-flash-tts"), 13.5)
        self.assertIn(f"about ${chars * 13.5 / 1e6:.2f}", line)
        self.assertIn("Gemini", line)

    def builds(self):
        try:
            with open(os.path.join(self.home, "workouts", ".logs", "builds.jsonl"), encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]
        except OSError:
            return []

    def test_a_render_that_fails_partway_records_what_it_sent(self):
        state = {"ok": 2}

        def answer(req):
            state["ok"] -= 1
            return wav_answer(req) if state["ok"] >= 0 else (401, {}, b'{"message": "Invalid api key"}')
        with FakeService(answer) as fake:
            out = self.render(fake.url, "--out", os.path.join(self.d, "x.mp3"))
        self.assertEqual(out.returncode, cli.SERVICE, out.stdout + out.stderr)
        rec = self.builds()[-1]
        self.assertTrue(rec["failed"])
        self.assertEqual(rec["route"], "fish")
        self.assertGreater(rec["chars_sent"], 0)
        self.assertGreaterEqual(rec["chars_sent"], rec["chars_rendered"])
        self.assertIn("usd_estimate", rec)
        self.assertFalse(os.path.exists(os.path.join(self.d, "x.build.json")))   # no MP3, no record beside it
        self.assertNotIn(SECRET, json.dumps(rec))

    def test_a_render_that_sent_nothing_records_nothing(self):
        self.set_ceiling(10)
        with FakeService(wav_answer) as fake:
            out = self.render(fake.url, "--out", os.path.join(self.d, "x.mp3"))
        self.assertEqual(out.returncode, cli.ISSUES, out.stdout + out.stderr)
        self.assertEqual(self.builds(), [])   # the first web build is still to come (the privacy line)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_interrupted_cloud_build_resumes_without_resending(self):
        state = {"ok": 3, "seen": 0}

        def answer(req):
            state["seen"] += 1
            if state["ok"] <= 0:
                return 503, {}, b"{}"
            state["ok"] -= 1
            return wav_answer(req)
        mp3 = os.path.join(self.d, "x.mp3")
        with FakeService(answer) as fake:
            first = self.render(fake.url, "--out", mp3, "--tolerance", "0.5")
            self.assertNotEqual(first.returncode, 0)
            cached = len(glob.glob(os.path.join(self.home, "workouts", ".audio-cache", "*.pcm")))
            self.assertEqual(cached, 3)
            sent_first = len([r for r in fake.requests if r.path == "/v1/tts"])
            state["ok"] = 1000
            second = self.render(fake.url, "--out", mp3, "--tolerance", "0.5")
        self.assertIn(second.returncode, (0, cli.DRIFT), second.stdout + second.stderr)
        first_to_render = int(first.stdout.split(" to render")[0].split()[-1])
        sent_second = len([r for r in fake.requests if r.path == "/v1/tts"]) - sent_first
        to_render = int(second.stdout.split(" to render")[0].split()[-1])
        self.assertEqual(to_render, first_to_render - 3)
        self.assertEqual(sent_second, to_render)
        self.assertIn("Sending", second.stdout)


if __name__ == "__main__":
    unittest.main()
