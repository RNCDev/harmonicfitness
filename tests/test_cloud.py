"""Cloud voices against local fake servers that mimic each service's documented API.
No network leaves the machine, and every key is a made-up test value."""
import base64
import contextlib
import glob
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import cli  # noqa: E402
import cloud  # noqa: E402
import coachpick  # noqa: E402
import personas  # noqa: E402
import helpers  # noqa: E402
import errors  # noqa: E402
from fakes import FakeService, tone_pcm, tone_wav  # noqa: E402
from test_personas import persona_home  # noqa: E402

SECRET = "sk-test-NEVERPRINT-123"
DRAFT = os.path.join(ROOT, "tests", "fixtures", "example.draft.txt")


def wav_answer(req):
    return 200, {"Content-Type": "audio/wav"}, tone_wav(0.4, rate=44100, bogus_size=True)


def table(case, rows):
    """Run each (name, check) row as its own subTest."""
    for name, row in rows:
        with case.subTest(name):
            row()


class Core(unittest.TestCase):
    def test_every_service_module_keeps_the_contract(self):
        import inspect
        import services
        for name in cloud.SERVICES:
            module = cloud.service_module(name)
            for fn, params in services.REQUIRED.items():
                with self.subTest(service=name, fn=fn):
                    self.assertEqual(list(inspect.signature(getattr(module, fn)).parameters)[:len(params)], params)
            self.assertIsInstance(getattr(module, "STORES_DRAFTS", False), bool)
        self.assertTrue(cloud.service_module("gemini").STORES_DRAFTS)
        with self.assertRaises(errors.CoachError):
            cloud.service_module("os")   # only a listed service, never any importable name

    def test_retries_only_when_nothing_could_be_sent_twice(self):
        import http.client
        import socket
        import urllib.error

        def a_429_then_success_is_retried():
            calls = []

            def answer(req):
                calls.append(1)
                return (429, {}, b"{}") if len(calls) < 3 else (200, {}, b"ok")
            with FakeService(answer) as fake:
                status, _, data = cloud.request("POST", fake.url + "/x", {}, b"", sleep=lambda s: None)
            self.assertEqual((status, data, len(calls)), (200, b"ok", 3))

        def a_long_retry_after_is_quota_not_a_sleep():
            slept = []
            with FakeService(lambda r: (429, {"Retry-After": "3600"}, b'{"message": "slow down"}')) as fake:
                with self.assertRaises(cloud.ServiceError) as got:
                    cloud.request("POST", fake.url + "/x", {}, b"{}", service="fish", sleep=slept.append)
            self.assertEqual(got.exception.kind, "quota")
            self.assertTrue(got.exception.listener_must_act)
            self.assertEqual(slept, [])
            self.assertIn("3600", str(got.exception))

        def a_save_is_retried_only_on_429():
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

        def a_save_retries_a_refused_connection_not_a_timeout():
            tries = []

            def refused(*a, **k):
                tries.append(1)
                raise urllib.error.URLError(ConnectionRefusedError(61, "refused"))
            with mock.patch.object(cloud, "_open", refused), self.assertRaises(cloud.ServiceError):
                cloud.request("POST", "http://127.0.0.1:9/x", {}, b"", sleep=lambda s: None, idempotent=False, tries=3)
            self.assertEqual(len(tries), 3)   # nothing was sent: safe to try again
            tries.clear()

            def timed_out(*a, **k):
                tries.append(1)
                raise socket.timeout("timed out")
            with mock.patch.object(cloud, "_open", timed_out), self.assertRaises(cloud.ServiceError):
                cloud.request("POST", "http://127.0.0.1:9/x", {}, b"", sleep=lambda s: None, idempotent=False, tries=3)
            self.assertEqual(len(tries), 1)

        def a_cut_off_answer_is_retried_only_when_safe():
            tries = []

            def cut_off(*a, **k):
                tries.append(1)
                raise http.client.IncompleteRead(b"RIFF")
            with mock.patch.object(cloud, "_open", cut_off), self.assertRaises(cloud.ServiceError) as got:
                cloud.request("POST", "http://127.0.0.1:9/x", {}, b"", sleep=lambda s: None, tries=3)
            self.assertEqual((len(tries), got.exception.kind), (3, "unavailable"))
            tries.clear()
            with mock.patch.object(cloud, "_open", cut_off), self.assertRaises(cloud.ServiceError):
                cloud.request("POST", "http://127.0.0.1:9/x", {}, b"", sleep=lambda s: None, tries=3, idempotent=False)
            self.assertEqual(len(tries), 1)   # a save may have landed: never sent twice
        def a_402_is_retried_only_while_running_requests_settle():
            settling = b'{"error": {"message": "This request would exceed your available credits given your current ' \
                       b'in-flight requests. Retry after in-flight requests settle, or add credits."}}'
            calls = []

            def answer(req):
                calls.append(1)
                return (402, {}, settling) if len(calls) < 3 else (200, {}, b"ok")
            with FakeService(answer) as fake:
                status, _, data = cloud.request("POST", fake.url + "/x", {}, b"", sleep=lambda s: None)
            self.assertEqual((status, data, len(calls)), (200, b"ok", 3))
            calls.clear()
            out = b'{"error": {"message": "Insufficient credits. Add more using https://openrouter.ai/credits"}}'
            with FakeService(lambda r: calls.append(1) or (402, {}, out)) as fake:
                with self.assertRaises(cloud.ServiceError) as got:
                    cloud.request("POST", fake.url + "/x", {}, b"", service="openrouter", sleep=lambda s: None)
            self.assertEqual((len(calls), got.exception.kind), (1, "billing"))   # out of credit: never sent again
        table(self, [("402 settling", a_402_is_retried_only_while_running_requests_settle),
                     ("429", a_429_then_success_is_retried), ("long wait", a_long_retry_after_is_quota_not_a_sleep),
                     ("save", a_save_is_retried_only_on_429), ("refused", a_save_retries_a_refused_connection_not_a_timeout),
                     ("cut off", a_cut_off_answer_is_retried_only_when_safe)])

    def test_a_stopping_render_ends_its_own_retries_and_no_other(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        stop, other = threading.Event(), threading.Event()

        def answer(req):
            stop.set()   # the render fails elsewhere while this request is out
            return 503, {}, b"{}"
        self.addCleanup(cloud.stop_on, None)
        cloud.stop_on(stop)
        with FakeService(answer) as fake, mock.patch.dict(os.environ, {"HARMONICFITNESS_RETRY_WAIT": "1"}):
            with self.assertRaises(cloud.ServiceError):
                cloud.request("POST", fake.url + "/x", {}, b"", service="fish")   # no backoff slept through
        self.assertEqual(len(fake.requests), 1)
        stop.clear()
        # the stop reaches a render's worker threads through its speaker, and stops no other render
        voice = {"service": "fish", "voice_id": "v", "model": "s2.1-pro"}
        with FakeService(answer) as fake, mock.patch.dict(os.environ, {"HARMONICFITNESS_FISH_URL": fake.url,
                                                                      "FISH_AUDIO_API_KEY": SECRET,
                                                                      "HARMONICFITNESS_RETRY_WAIT": "0"}):
            cloud.stop_on(stop)
            say = cloud.speaker(voice)
            with ThreadPoolExecutor(1) as pool, self.assertRaises(cloud.ServiceError):
                pool.submit(say, "Hi.", 1).result()   # a worker thread, as render_cloud runs it
            self.assertEqual(len(fake.requests), 1)   # no retry once its own render stopped
            fake.requests.clear()   # a request in another thread, outside that render, isn't stopped by it
            with ThreadPoolExecutor(1) as pool, self.assertRaises(cloud.ServiceError):
                pool.submit(cloud.request, "POST", fake.url + "/x", {}, b"", service="fish").result()
            self.assertEqual(len(fake.requests), cloud.TRIES)
            cloud.stop_on(other)   # another render, whose stop isn't set: it retries as usual
            fake.requests.clear()
            with ThreadPoolExecutor(1) as pool, self.assertRaises(cloud.ServiceError):
                pool.submit(cloud.speaker(voice), "Hi.", 1).result()
            self.assertEqual(len(fake.requests), cloud.TRIES)

    def test_a_redirect_is_never_followed(self):
        with FakeService(lambda r: (200, {}, b"{}")) as elsewhere:
            with FakeService(lambda r: (302, {"Location": elsewhere.url + "/stolen"}, b"")) as fake:
                with self.assertRaises(cloud.ServiceError) as got:
                    cloud.request("POST", fake.url + "/x", {"Authorization": f"Bearer {SECRET}"}, b"{}",
                                  service="fish", sleep=lambda s: None)
        self.assertEqual(elsewhere.requests, [])   # the key never went there
        self.assertEqual(len(fake.requests), 1)    # and it isn't retried
        self.assertEqual(got.exception.kind, "unavailable")
        self.assertIn("redirected to 127.0.0.1; not followed", str(got.exception))

    def test_feeds_follow_a_redirect_only_to_http_or_https(self):
        import feeds
        with FakeService(lambda r: (200, {}, b"the feed")) as there:
            with FakeService(lambda r: (301, {"Location": there.url + "/feed"}, b"")) as fake:
                self.assertEqual(feeds.fetch(fake.url + "/old"), b"the feed")
                fake.answer = lambda r: (302, {"Location": "ftp://127.0.0.1/feed"}, b"")
                with self.assertRaises(ValueError) as got:
                    feeds.fetch(fake.url + "/old")
        self.assertIn("only http and https", str(got.exception))

    def test_an_address_override_must_be_https_or_this_computer(self):
        for url in ("http://evil.example", "http://10.0.0.5:8080", "ftp://127.0.0.1/x", "file:///tmp/x"):
            with mock.patch.dict(os.environ, {"HARMONICFITNESS_FISH_URL": url}), self.assertRaises(cloud.ServiceError) as got:
                cloud.base_url("fish")
            self.assertEqual(got.exception.kind, "bad_request")
            self.assertIn("HARMONICFITNESS_FISH_URL", str(got.exception))
        for url in ("https://proxy.example/", "http://127.0.0.1:9", "http://localhost:9"):
            with mock.patch.dict(os.environ, {"HARMONICFITNESS_FISH_URL": url}):
                self.assertEqual(cloud.base_url("fish"), url.rstrip("/"))
        with mock.patch.dict(os.environ, {"HARMONICFITNESS_FISH_URL": ""}):
            self.assertEqual(cloud.base_url("fish"), "https://api.fish.audio")

    def test_a_tls_fallback_says_so(self):
        import ssl
        cloud._tls.cache_clear()
        self.addCleanup(cloud._tls.cache_clear)
        err = io.StringIO()
        with mock.patch.object(ssl, "create_default_context", side_effect=OSError("no bundle")), \
                contextlib.redirect_stderr(err):
            self.assertIsNone(cloud._tls())
        self.assertIn("certifi", err.getvalue())

    def test_the_shipped_services_file_validates_and_a_bad_table_doesnt(self):
        import copy
        import services
        shipped = services.settings()
        self.assertEqual(services.validate(shipped), [])
        bad = copy.deepcopy(shipped)
        bad["fish"].update(url="http://api.fish.audio", concurrency="5", candidates=0, unit="words")
        del bad["inworld"]["key_var"]
        bad["gemini"]["default_model"] = "not-a-model"
        problems = " | ".join(services.validate(bad))
        for want in ("[fish] url", "[fish] concurrency", "[fish] candidates", "[fish] unit", "[inworld] key_var",
                     "[gemini] default_model"):
            self.assertIn(want, problems)
        self.assertEqual(services.validate({"elevenlabs": dict(shipped["elevenlabs"], tried_live="yes")}),
                         ["[elevenlabs] tried_live must be true or false (it's 'yes')"])
        design = " | ".join(services.validate({"elevenlabs": dict(shipped["elevenlabs"], design_model="",
                                                                   design_guidance=-1, design_line="Too short.")}))
        for want in ("[elevenlabs] design_model", "[elevenlabs] design_guidance", "[elevenlabs] design_line"):
            self.assertIn(want, design)

    def test_errors_by_kind(self):
        for status, body, kind in ((401, b'{"message": "Invalid api key"}', "auth"),
                                   (402, b'{"status": 402, "message": "No payment"}', "billing"),   # Fish's 402
                                   (400, b'{"detail": {"message": "text too long"}}', "bad_request"),
                                   (400, b'{"error_code": "quota_exceeded", "message": "out"}', "quota"),
                                   (503, b"{}", "unavailable"),
                                   # 0.76.0: an outage page that mentions a quota is still an outage
                                   (503, b'{"message": "quota service is down"}', "unavailable"),
                                   # and a bad request echoing the script's own words is still a bad request
                                   (400, b'{"message": "invalid text: the payment of quota debts"}', "bad_request"),
                                   (403, b'{"message": "monthly quota reached"}', "quota"),
                                   (400, b'{"error": {"code": "insufficient_credits", "message": "x"}}', "billing")):
            with FakeService(lambda req, s=status, b=body: (s, {}, b)) as fake:
                with self.assertRaises(cloud.ServiceError) as e:
                    cloud.request("POST", fake.url + "/x", {"Authorization": f"Bearer {SECRET}"}, b"",
                                  service="fish", sleep=lambda s: None)
            self.assertEqual(e.exception.kind, kind, status)
            self.assertNotIn(SECRET, str(e.exception))
            if kind in ("auth", "billing", "quota"):
                self.assertEqual(e.exception.exit_code, cli.SERVICE, status)

    def test_estimate_counts_bytes_for_fish_and_characters_elsewhere(self):
        chars, usd = cloud.estimate("fish", "s2.1-pro", ["Zoë"] * 1000)
        self.assertEqual(chars, 3000)
        self.assertAlmostEqual(usd, 4000 * 15 / 1e6)
        _, usd = cloud.estimate("inworld", "inworld-tts-2", ["abc"] * 1000)
        self.assertAlmostEqual(usd, 3000 * 25 / 1e6)
        _, usd = cloud.estimate("gemini", "gemini-3.8-flash-tts", ["abc"] * 1000)
        self.assertAlmostEqual(usd, 3000 * 13.5 / 1e6)


VOICE_IDS = {"fish": "fish-model-1", "elevenlabs": "el-voice-1", "gemini": "gemini-voice-1",
             "inworld": "workspace__design-voice-1", "openrouter": "brian"}
COACHES = {"fish": "Coach Reed", "elevenlabs": "Coach Ellis", "gemini": "Coach Nolan", "inworld": "Coach Owen",
           "openrouter": "Coach Rowan"}


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

    def test_a_web_coach_s_voice(self):
        def by_its_saved_voice_id():
            web_coach(self.folder, "inworld")
            p = personas.lookup("Coach Owen")
            v = personas.voice_for(p, "fish")   # the route is ignored: a web coach speaks through its service
            self.assertEqual({k: v[k] for k in ("name", "persona", "engine", "backend", "route", "service", "model",
                                                "voice_id", "style", "revision", "generate", "concurrency", "max_chars")},
                             {"name": "Coach Owen", "persona": "coach-owen-inworld", "engine": "inworld",
                              "backend": "cloud", "route": "inworld", "service": "inworld", "model": "inworld-tts-2",
                              "voice_id": VOICE_IDS["inworld"], "style": "", "revision": None, "generate": {},
                              "concurrency": 5, "max_chars": 2000})
            self.assertEqual(v["key"], cloud.web_key(p, "inworld-tts-2"))
            self.assertEqual((v["persona_dir"], v["pace_file"]), (p.folder, p.pace_file))
            self.assertNotIn("ref_audio", v)
            self.assertEqual(cloud.voice_for(p, "inworld"), v)

        def a_voice_id_a_service_never_gives_stops():
            for bad in ("../voices/x", "a/b", "id?x=1", "x" * 129):
                web_coach(self.folder, "elevenlabs", voice_id=bad)
                with self.assertRaises(errors.CoachError):
                    personas.voice_for(personas.lookup("Coach Ellis"), "elevenlabs")
            web_coach(self.folder, "elevenlabs", voice_id="voice_Ab9.c:d-e")
            self.assertEqual(personas.voice_for(personas.lookup("Coach Ellis"), "elevenlabs")["voice_id"],
                             "voice_Ab9.c:d-e")

        def a_chosen_model_changes_the_key():
            web_coach(self.folder, "elevenlabs", model="eleven_v4_turbo")
            p = personas.lookup("Coach Ellis")
            v = personas.voice_for(p, "elevenlabs")
            self.assertEqual(v["model"], "eleven_v4_turbo")
            self.assertEqual(v["key"], cloud.web_key(p, "eleven_v4_turbo"))
            self.assertNotEqual(v["key"], cloud.web_key(p, "eleven_v4"))

        def no_voice_yet_stops():
            import context
            path = os.path.join(self.folder, "coach-reed-fish")
            os.makedirs(path)
            with open(os.path.join(path, "persona.md"), "w", encoding="utf-8") as f:
                f.write(context.persona_text({"name": "Coach Reed", "kind": "web", "service": "fish",
                                              "placeholder": True, "pending": "design"}, "## How this coach talks\n"))
            with self.assertRaises(errors.PROBLEMS) as e:
                personas.voice_for(personas.lookup("Coach Reed"), "fish")
            self.assertIn("Coach Reed", str(e.exception.code))
            self.assertIn("audition", str(e.exception.code))
        table(self, [("saved id", by_its_saved_voice_id), ("bad id", a_voice_id_a_service_never_gives_stops),
                     ("model", a_chosen_model_changes_the_key), ("no voice", no_voice_yet_stops)])

    def test_a_local_coach_never_renders_on_a_web_route(self):
        with self.assertRaises(errors.PROBLEMS) as e:
            personas.voice_for(personas.lookup("Coach Test"), "fish")
        self.assertIn("local coach", str(e.exception.code))
        self.assertEqual(personas.voice_for(personas.lookup("Coach Test"), "local")["route"], "local")


FISH_WAVS = [tone_wav(1.0, rate=44100), tone_wav(0.8, rate=44100)]
INWORLD_WAVS = [tone_wav(0.9), tone_wav(0.7)]


def fish_design_answer(req):
    candidate = lambda i: {"id": f"cand-{i}", "index": i, "audio_base64": b64(FISH_WAVS[i]), "sample_rate": 44100,
                           "duration_ms": 1000, "text": "Okay, set your feet.", "language": "en",
                           "instruct": "x", "features": {}, "audio_token_sha256": "abc", "signature": f"sig-{i}"}
    return 200, {"Content-Type": "application/json"}, json.dumps({"candidates": [candidate(0), candidate(1)]}).encode()


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


def gemini_design_answer(req):
    if req.path == "/v1beta/voices":
        return 200, {}, json.dumps({"id": "voice-abc", "model": "gemini-3.8-flash-tts", "type": "prompted",
                                    "expire_time": "2026-11-25T00:00:00Z", "display_name": "x",
                                    "prompted": {"input": "x"}, "usage": {},
                                    "sample_audio": {"mime_type": "audio/wav", "data": b64(tone_wav(2.0))}}).encode()
    if req.path == "/v1beta/interactions":
        return 200, {}, gemini_audio_answer(tone_wav(1.0))
    return 404, {}, b"{}"


def inworld_answer(req):
    if req.path == "/voices/v1/voices:design":
        return 200, {}, json.dumps({"previewVoices": [{"voiceId": f"ws__design-{i}", "previewText": "Okay, set.",
                                                       "previewAudio": b64(INWORLD_WAVS[i])} for i in range(2)]}).encode()
    if req.path.endswith(":publish"):
        return 200, {}, json.dumps({"voiceId": req.path.split("/")[-1].split(":")[0], "displayName": "x"}).encode()
    if req.path == "/tts/v1/voice":
        return 200, {}, json.dumps({"audioContent": b64(tone_wav(0.3)), "usage": {}}).encode()
    return 404, {}, b"{}"


def openrouter_answer(req):
    if req.path == "/api/v1/audio/speech":
        if json.loads(req.body)["model"].startswith("google/"):   # Gemini sends only raw PCM, its rate in the type
            return 200, {"Content-Type": "audio/pcm;rate=48000;channels=1"}, tone_pcm(0.6, rate=48000)
        return 200, {"Content-Type": "audio/wav"}, tone_wav(0.6)
    if req.path == "/api/v1/credits":
        return 200, {"Content-Type": "application/json"}, json.dumps(
            {"data": {"total_credits": 25, "total_usage": 7.5}}).encode()
    return 404, {}, b'{"error": {"code": 404, "message": "not found"}}'


class Services(unittest.TestCase):
    """Each web service against a fake of its documented API: a web coach and a test key on every one."""

    def setUp(self):
        import keys
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.folder = persona_home(self.d)
        for service in COACHES:
            web_coach(self.folder, service)
        env = {var: SECRET for var in keys.SERVICE_VARS.values()}
        env["HARMONICFITNESS_RETRY_WAIT"] = "0"
        for p in (mock.patch.object(personas.paths, "PERSONAS", self.folder), mock.patch.dict(os.environ, env)):
            p.start()
            self.addCleanup(p.stop)

    @staticmethod
    def module(service):
        import importlib
        return importlib.import_module(f"services.{service}")

    def voice(self, service):
        return personas.voice_for(personas.lookup(COACHES[service]), service)

    def serve(self, service, answer):
        fake = FakeService(answer)
        fake.__enter__()
        self.addCleanup(fake.__exit__)
        patch = mock.patch.dict(os.environ, {f"HARMONICFITNESS_{service.upper()}_URL": fake.url})
        patch.start()
        self.addCleanup(patch.stop)
        return fake

    def check_candidate(self, c, text):
        self.assertEqual(set(c), {"pcm", "wav", "text", "draft_id", "signature"})
        self.assertEqual(c["text"], text)
        self.assertGreater(len(c["pcm"]), 0)
        pcm, rate = cloud.wav_pcm(c["wav"])
        self.assertGreater(len(pcm), 0)

    def test_inworld_refuses_a_paragraph_over_2000_characters_before_sending(self):
        fake = self.serve("inworld", inworld_answer)
        with self.assertRaises(cloud.ServiceError) as e:
            cloud.speaker(self.voice("inworld"))("word " * 401, 42)
        self.assertEqual(e.exception.kind, "bad_request")
        self.assertIn("2000", str(e.exception))
        self.assertEqual(fake.requests, [])

    def test_openrouter_refuses_an_unknown_voice_before_sending(self):
        fake = self.serve("openrouter", openrouter_answer)
        with self.assertRaises(cloud.ServiceError):
            self.module("openrouter").speaker({"voice_id": "nobody", "model": "elevenlabs/eleven-v4"})
        self.assertEqual(fake.requests, [])

    def test_gemini_never_deletes_one_of_its_own_voices(self):
        """The ready-made coaches speak with Gemini's own voices (prebuilt, or the voice library's by id): they
        belong to no account, so a delete sends nothing."""
        gemini = self.module("gemini")
        for own in ("achird", "Kore", "en-gb-tutor-16", "en-us-assistant-1"):
            self.assertTrue(gemini.own_voice(own), own)
        for stored in ("voice_abc123", "voice-abc", "gemini-voice-1", "", None):
            self.assertFalse(gemini.own_voice(stored), stored)
        fake = self.serve("gemini", lambda req: (500, {}, b"no"))
        self.assertTrue(gemini.delete("en-gb-tutor-16"))
        self.assertEqual(fake.requests, [])

    def test_balances_carry_a_refusal_without_the_key(self):
        import balances
        self.serve("fish", lambda r: (401, {}, json.dumps({"message": f"bad key {SECRET}"}).encode()))
        with mock.patch("keys.is_set", lambda s: s == "fish"):
            row = balances.balances()["fish"]
        self.assertEqual((row["ok"], row["kind"]), (False, "auth"))
        self.assertNotIn(SECRET, json.dumps(row))
        self.assertIn("billing", balances.line(row))

    def test_a_save_or_design_is_never_retried_after_sending(self):
        def saved_once(service, call, saved):
            """A 500 isn't retried (the service may have saved it), a 429 is."""
            fake = self.serve(service, lambda r: (500, {}, b'{"message": "oops"}'))
            with self.assertRaises(cloud.ServiceError):
                call()
            self.assertEqual(len(fake.requests), 1)
            answers = iter([(429, {}, b"{}")])
            fake.answer = lambda r: next(answers, None) or saved(r)
            call()
            path = fake.requests[0].path
            self.assertEqual(len([r for r in fake.requests if r.path == path]), 3)
        fish, elevenlabs, gemini, inworld = (self.module(s) for s in ("fish", "elevenlabs", "gemini", "inworld"))
        fish_c = {"pcm": b"", "wav": FISH_WAVS[0], "text": "x", "draft_id": "d-1", "signature": "sig"}
        el_c = {"pcm": b"", "wav": b"", "text": "x", "draft_id": "g1", "signature": None}
        for service, call, saved in (
                ("fish", lambda: fish.save(fish_c, "Coach Reed", "A man.", FISH_WAVS[0]),
                 lambda r: (201, {}, b'{"_id": "model-1"}')),
                ("elevenlabs", lambda: elevenlabs.save(el_c, "Coach Ellis", "A man.", b""),
                 lambda r: (200, {}, b'{"voice_id": "el-1"}')),
                ("gemini", lambda: gemini.design("A man.", "Okay.", 1, "label"), gemini_design_answer),
                ("inworld", lambda: inworld.save(fish_c, "Coach Owen", "A man.", b""), lambda r: (200, {}, b"{}"))):
            with self.subTest(service):
                saved_once(service, call, saved)
        for module in (fish, elevenlabs, inworld):   # every billed design call is sent once
            with self.subTest(module.__name__), \
                    mock.patch.object(cloud, "request", side_effect=RuntimeError("stop")) as req:
                with self.assertRaises(RuntimeError):
                    module.design("a coach", "a line", 1)
            self.assertFalse(req.call_args.kwargs.get("idempotent", True), module.__name__)

    def test_429(self):
        inworld = self.module("inworld")

        def a_short_wait_is_waited_through():
            calls = []

            def answer(req):
                calls.append(1)
                if len(calls) == 1:   # a Google-style rate limit: "quota" in the body, a short Retry-After
                    return 429, {"Retry-After": "1"}, b'{"code": 8, "message": "RESOURCE_EXHAUSTED: Quota exceeded"}'
                return inworld_answer(req)
            self.serve("inworld", answer)
            self.assertEqual(len(inworld.design("A man.", "Okay.", 2, "label")), 2)
            self.assertEqual(len(calls), 2)

        def naming_no_wait_is_retried_before_it_counts_as_quota():
            calls = []

            def answer(req):
                calls.append(1)
                if len(calls) == 1:   # "quota" in the body and no Retry-After: a per-minute limit, not an empty account
                    return 429, {}, b'{"message": "Rate quota exceeded"}'
                return inworld_answer(req)
            self.serve("inworld", answer)
            self.assertEqual(len(inworld.design("A man.", "Okay.", 2, "label")), 2)
            self.assertEqual(len(calls), 2)
            self.serve("inworld", lambda r: (429, {}, b'{"message": "Rate quota exceeded"}'))
            with self.assertRaises(cloud.ServiceError) as e:   # every try refused: now it's the quota
                inworld.design("A man.", "Okay.", 2, "label")
            self.assertEqual(e.exception.kind, "quota")

        def a_long_wait_is_quota():
            self.serve("inworld", lambda r: (429, {"Retry-After": "86400"}, b'{"message": "Quota exceeded for the month"}'))
            with self.assertRaises(cloud.ServiceError) as e:
                inworld.design("A man.", "Okay.", 2, "label")
            self.assertEqual(e.exception.kind, "quota")
            self.assertEqual(e.exception.exit_code, cli.SERVICE)
        table(self, [("short wait", a_short_wait_is_waited_through),
                     ("no wait", naming_no_wait_is_retried_before_it_counts_as_quota), ("long wait", a_long_wait_is_quota)])

    def test_speech_requests_as_each_service_documents_them(self):
        def fish():
            fake = self.serve("fish", wav_answer)
            pcm = cloud.speaker(self.voice("fish"))("Set your feet.", 42, previous_text="Hi.", next_text="Rest.")
            req = fake.requests[0]
            self.assertEqual((req.method, req.path), ("POST", "/v1/tts"))
            self.assertEqual(req.headers["authorization"], f"Bearer {SECRET}")
            self.assertEqual(req.headers["model"], "s2.1-pro")
            self.assertEqual(req.headers["content-type"], "application/json")
            self.assertEqual(json.loads(req.body), {"text": "Set your feet.", "reference_id": VOICE_IDS["fish"],
                                                    "format": "wav", "sample_rate": 24000})
            self.assertAlmostEqual(len(pcm) / 2 / 24000, 0.4, delta=0.05)   # resampled to 24 kHz

        def elevenlabs():   # neighbors and seed, and never a clone first
            fake = self.serve("elevenlabs", elevenlabs_answer)
            pcm = cloud.speaker(self.voice("elevenlabs"))("Two more.", 42, previous_text="Set your feet.",
                                                          next_text="Rest.")
            req = fake.requests[0]
            self.assertEqual(req.path, f"/v1/text-to-speech/{VOICE_IDS['elevenlabs']}?output_format=pcm_24000")
            self.assertEqual(req.headers["xi-api-key"], SECRET)
            self.assertEqual(json.loads(req.body), {"text": "Two more.", "model_id": "eleven_v4", "seed": 42,
                                                    "previous_text": "Set your feet.", "next_text": "Rest."})
            self.assertGreater(len(pcm), 0)
            self.assertEqual(len(fake.requests), 1)

        def gemini():   # the audio found anywhere in the answer
            fake = self.serve("gemini", lambda r: (200, {}, gemini_audio_answer(tone_wav(0.5, rate=44100))))
            pcm = cloud.speaker(self.voice("gemini"))("Set your feet.", 42, previous_text="Hi.", next_text="Rest.")
            self.assertAlmostEqual(len(pcm) / 2 / 24000, 0.5, delta=0.05)
            req = fake.requests[0]
            self.assertEqual((req.path, req.headers["x-goog-api-key"]), ("/v1beta/interactions", SECRET))
            self.assertEqual(json.loads(req.body), {"model": "gemini-3.8-flash-tts",
                                                    "input": [{"type": "text", "text": "Set your feet."}],
                                                    "response_modalities": ["audio"],
                                                    "generation_config": {"speech_config": [{"voice": VOICE_IDS["gemini"]}]}})

        def inworld():   # LINEAR16 at 24 kHz, Basic auth with the key as given
            fake = self.serve("inworld", inworld_answer)
            say = cloud.speaker(self.voice("inworld"))
            pcm = say("Two more.", 42, previous_text="Set your feet.", next_text="Rest.")
            say("First.", 42)
            first, second = (json.loads(r.body) for r in fake.requests)
            self.assertEqual(fake.requests[0].path, "/tts/v1/voice")
            self.assertEqual(first, {"text": "Two more.", "voiceId": VOICE_IDS["inworld"], "modelId": "inworld-tts-2",
                                     "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000},
                                     "synthesisContext": {"previousRequests": [{"text": "Set your feet."}]}})
            self.assertNotIn("synthesisContext", second)
            self.assertAlmostEqual(len(pcm) / 2 / 24000, 0.3, delta=0.05)
            self.module("inworld").design("A man.", "Okay.", 2, "label")
            self.assertTrue(all(r.headers["authorization"] == f"Basic {SECRET}" for r in fake.requests))

        def openrouter():   # a stock voice as MP3; an MAI voice billed as MAI; a mismatched model refused
            fake = self.serve("openrouter", openrouter_answer)
            v = self.voice("openrouter")
            self.assertEqual((v["voice_id"], v["model"]), ("brian", "elevenlabs/eleven-v4-turbo"))   # turbo first, 0.46.2
            self.assertEqual(cloud.powered_by("openrouter", v["model"]), "ElevenLabs")
            self.assertEqual(cloud.powered_by("openrouter", "microsoft/mai-voice-2.1"), "Microsoft MAI")
            self.assertIsNone(cloud.powered_by("fish", "s2"))   # a service that speaks its own voices
            self.assertGreater(len(cloud.speaker(v)("Two more.", 1)), 0)
            req = fake.requests[-1]
            self.assertEqual((req.method, req.path), ("POST", "/api/v1/audio/speech"))
            self.assertEqual(req.headers["authorization"], f"Bearer {SECRET}")
            self.assertEqual(json.loads(req.body), {"model": "elevenlabs/eleven-v4-turbo", "input": "Two more.",
                                                    "voice": "brian", "response_format": "mp3"})
            web_coach(self.folder, "openrouter", name="Coach Iris", voice_id="en-US-Iris:MAI-Voice-2.1")
            v = personas.voice_for(personas.lookup("Coach Iris"), "openrouter")
            self.assertEqual(v["model"], "microsoft/mai-voice-2.1")
            cloud.speaker(v)("Rest.", 1)
            self.assertEqual(json.loads(fake.requests[-1].body)["model"], "microsoft/mai-voice-2.1")
            # a coach naming a model that can't speak its voice is refused, never quietly swapped
            m = self.module("openrouter")
            with self.assertRaises(cloud.ServiceError) as got:
                m._model({"voice_id": "en-US-Iris:MAI-Voice-2.1", "model": "elevenlabs/eleven-v4-turbo"})
            self.assertIn("microsoft/mai-voice-2.1", str(got.exception))
            self.assertEqual(m._model({"voice_id": "brian", "model": "elevenlabs/eleven-v4-turbo"}),
                             "elevenlabs/eleven-v4-turbo")
            # a Gemini voice: asked for as raw PCM (all Gemini sends), read at the rate its reply names
            web_coach(self.folder, "openrouter", name="Coach Gale", voice_id="Sulafat")
            v = personas.voice_for(personas.lookup("Coach Gale"), "openrouter")
            self.assertEqual(v["model"], "google/gemini-3.8-flash-lite-tts")
            self.assertEqual(cloud.powered_by("openrouter", v["model"]), "Google Gemini")
            self.assertEqual((cloud.voice_gender("openrouter", "Sulafat"), cloud.voice_gender("openrouter", "Iapetus"),
                              cloud.voice_gender("openrouter", "nobody"), cloud.voice_gender("fish", "x")),
                             ("f", "m", None, None))   # the hosted Coaches page's Women and Men
            pcm = cloud.speaker(v)("Rest.", 1)
            self.assertEqual(json.loads(fake.requests[-1].body)["response_format"], "pcm")
            self.assertAlmostEqual(len(pcm) / 2 / cloud.SR, 0.6, delta=0.1)   # 48 kHz read as 48 kHz, not 24
        table(self, [("fish", fish), ("elevenlabs", elevenlabs), ("gemini", gemini), ("inworld", inworld),
                     ("openrouter", openrouter)])

    def test_design(self):
        def fish():   # keeps each candidate's signature and the exact WAV Fish sent: the save sends it back
            fake = self.serve("fish", fish_design_answer)
            out = self.module("fish").design("A warm coach in her forties.", "Okay, set your feet.", 2, "ignored")
            req = fake.requests[0]
            self.assertEqual((req.path, req.headers["model"]), ("/v1/voice-design", "voice-design-1"))
            self.assertEqual(req.headers["authorization"], f"Bearer {SECRET}")
            self.assertEqual(json.loads(req.body), {"instruction": "A warm coach in her forties.",
                                                    "reference_text": "Okay, set your feet.", "language": "en", "n": 2})
            self.assertEqual(len(out), 2)
            for i, c in enumerate(out):
                self.check_candidate(c, "Okay, set your feet.")
                self.assertEqual(c["wav"], FISH_WAVS[i])
                self.assertEqual((c["signature"], c["draft_id"]), (f"sig-{i}", f"cand-{i}"))
            self.assertAlmostEqual(len(out[0]["pcm"]) / 2 / 24000, 1.0, delta=0.15)

        def elevenlabs():   # three previews, each a candidate, by services.toml's design settings
            fake = self.serve("elevenlabs", elevenlabs_answer)
            out = self.module("elevenlabs").design("A warm coach in her forties.", "Okay, set your feet.", 2, "ignored")
            req = fake.requests[0]
            self.assertEqual(req.path, "/v1/text-to-voice/design?output_format=pcm_24000")
            body = json.loads(req.body)
            s = cloud.services()["elevenlabs"]
            self.assertEqual(set(body), {"voice_description", "text", "model_id", "guidance_scale"})
            self.assertEqual(body["voice_description"], "A warm coach in her forties.")
            self.assertEqual((body["model_id"], body["guidance_scale"]), (s["design_model"], s["design_guidance"]))
            self.assertLess(body["guidance_scale"], 5)
            self.assertEqual(body["text"], s["design_line"])
            self.assertGreaterEqual(len(body["text"]), 100)
            self.assertEqual([c["draft_id"] for c in out], ["g0", "g1", "g2"])
            for c in out:
                self.check_candidate(c, "the words spoken")
                self.assertIsNone(c["signature"])
            self.assertAlmostEqual(len(cloud.wav_pcm(out[0]["wav"])[0]) / 2 / 24000, len(out[0]["pcm"]) / 2 / 24000,
                                   delta=0.01)

        def gemini():   # only input in prompted; the line spoken once by the new voice
            fake = self.serve("gemini", gemini_design_answer)
            out = self.module("gemini").design("A man in his forties.", "Okay, set your feet.", 1,
                                               "harmonicfitness audition a1 C")
            create, speech = fake.requests
            self.assertEqual((create.method, create.path), ("POST", "/v1beta/voices"))
            self.assertEqual(create.headers["x-goog-api-key"], SECRET)
            self.assertEqual(json.loads(create.body), {"voice": {"type": "prompted",
                                                                 "display_name": "harmonicfitness audition a1 C",
                                                                 "prompted": {"input": "A man in his forties."}},
                                                       "store": True})
            self.assertEqual(speech.path, "/v1beta/interactions")
            body = json.loads(speech.body)
            self.assertEqual(body["generation_config"], {"speech_config": [{"voice": "voice-abc"}]})
            self.assertEqual(body["input"], [{"type": "text", "text": "Okay, set your feet."}])
            self.assertEqual(len(out), 1)
            self.check_candidate(out[0], "Okay, set your feet.")
            self.assertEqual((out[0]["draft_id"], out[0]["signature"]), ("voice-abc", None))
            self.assertAlmostEqual(len(out[0]["pcm"]) / 2 / 24000, 1.0, delta=0.15)   # the line, not sample_audio

        def gemini_failing_speech():   # the stored voice isn't left behind; if its delete fails, the listener is told
            def answer(req):
                if req.path == "/v1beta/interactions":
                    return 400, {}, b'{"error": {"message": "bad speech"}}'
                return gemini_design_answer(req)
            fake = self.serve("gemini", answer)
            with self.assertRaises(cloud.ServiceError):
                self.module("gemini").design("A man in his forties.", "Okay, set your feet.", 1, "label")
            self.assertEqual([(r.method, r.path) for r in fake.requests if r.method == "DELETE"],
                             [("DELETE", "/v1beta/voices/voice-abc")])
            fake.answer = lambda req: ((500, {}, b'{"error": {"message": "delete broke"}}') if req.method == "DELETE"
                                       else answer(req))
            err = io.StringIO()
            with self.assertRaises(cloud.ServiceError) as e, contextlib.redirect_stderr(err):
                self.module("gemini").design("A man in his forties.", "Okay, set your feet.", 1, "label")
            self.assertIn("bad speech", str(e.exception))
            self.assertIn('(Gemini keeps a voice "label", ID voice-abc: delete it there by hand.)', err.getvalue())

        def inworld():
            fake = self.serve("inworld", inworld_answer)
            out = self.module("inworld").design("A man in his forties.", "Okay, set your feet.", 2, "ignored")
            self.assertEqual(json.loads(fake.requests[0].body), {"designPrompt": "A man in his forties.",
                                                                 "previewText": "Okay, set your feet.",
                                                                 "languageCode": "EN_US", "numberOfSamples": 2})
            self.assertEqual([c["draft_id"] for c in out], ["ws__design-0", "ws__design-1"])
            for i, c in enumerate(out):
                self.check_candidate(c, "Okay, set.")
                self.assertEqual(c["wav"], INWORLD_WAVS[i])

        def openrouter():   # matches the description to stock voices and saves nothing
            fake = self.serve("openrouter", openrouter_answer)
            m = self.module("openrouter")
            self.assertEqual(m.match("A man in his forties, warm baritone, American accent", 1), ["brian"])
            self.assertIn(m.match("A British woman, warm and smooth", 1)[0], ("lily", "alice"))
            three = m.match("A young Australian man, natural and confident", 3)
            self.assertEqual(three[0], "charlie")
            self.assertEqual(len(three), 3)
            self.assertIn(three[2], m.VOICES["gemini"])
            self.assertEqual(m.VOICES["gemini"][three[2]][0], "m")
            cands = m.design("A man in his forties, warm baritone, American accent", "Set your feet.", 3, "label")
            self.assertEqual([c["draft_id"] for c in cands][:1], ["brian"])
            for c in cands:
                self.check_candidate(c, "Set your feet.")
            self.assertEqual({r.path for r in fake.requests}, {"/api/v1/audio/speech"})
            self.assertEqual(len(fake.requests), 3)
            self.assertEqual(m.save(cands[0], "Coach Rowan"), "brian")
            self.assertTrue(m.delete("brian"))
            self.assertEqual(len(fake.requests), 3)
        table(self, [("fish", fish), ("elevenlabs", elevenlabs), ("gemini", gemini),
                     ("gemini failing", gemini_failing_speech), ("inworld", inworld), ("openrouter", openrouter)])

    def test_save(self):
        def fish():   # a private model, multipart, with the design's signature
            fake = self.serve("fish", lambda r: (201, {}, json.dumps({"_id": "model-77", "state": "trained",
                                                                      "visibility": "private"}).encode()))
            candidate = {"pcm": b"\x00\x01" * 10, "wav": FISH_WAVS[0], "text": "Okay, set your feet.",
                         "draft_id": "cand-0", "signature": "sig-0"}
            self.assertEqual(self.module("fish").save(candidate, "Coach Reed", "A man in his forties.", FISH_WAVS[0]),
                             "model-77")
            req = fake.requests[0]
            self.assertEqual((req.method, req.path), ("POST", "/model"))
            self.assertEqual(req.headers["authorization"], f"Bearer {SECRET}")
            self.assertTrue(req.headers["content-type"].startswith("multipart/form-data; boundary="))
            for field, value in (("visibility", "private"), ("type", "tts"), ("title", "harmonicfitness Coach Reed"),
                                 ("train_mode", "fast"), ("texts", "Okay, set your feet."),
                                 ("voice_design_signatures", "sig-0")):
                self.assertIn(f'name="{field}"\r\n\r\n{value}\r\n'.encode(), req.body, field)
            self.assertIn(b'name="voices"; filename="voice.wav"\r\nContent-Type: audio/wav\r\n\r\n' + FISH_WAVS[0],
                          req.body)

        def elevenlabs():
            fake = self.serve("elevenlabs", elevenlabs_answer)
            candidate = {"pcm": b"\x00\x01", "wav": b"", "text": "x", "draft_id": "g1", "signature": None}
            self.assertEqual(self.module("elevenlabs").save(candidate, "Coach Ellis", "D" * 1500, b""), "el-saved-5")
            req = fake.requests[0]
            self.assertEqual((req.method, req.path), ("POST", "/v1/text-to-voice"))
            self.assertEqual(json.loads(req.body), {"voice_name": "harmonicfitness Coach Ellis",
                                                    "voice_description": "D" * 1000, "generated_voice_id": "g1"})

        def gemini():   # stored at design time
            fake = self.serve("gemini", gemini_design_answer)
            candidate = {"pcm": b"", "wav": b"", "text": "x", "draft_id": "voice-abc", "signature": None}
            self.assertEqual(self.module("gemini").save(candidate, "Coach Nolan", "A man.", b""), "voice-abc")
            self.assertEqual(fake.requests, [])

        def inworld():   # publish, with an edited draft ID kept to one path segment
            fake = self.serve("inworld", inworld_answer)
            out = self.module("inworld").design("A man in his forties.", "Okay, set your feet.", 2, "ignored")
            self.assertEqual(self.module("inworld").save(out[1], "Coach Owen", "A man in his forties.", out[1]["wav"]),
                             "ws__design-1")
            publish = fake.requests[-1]
            self.assertEqual((publish.method, publish.path), ("POST", "/voices/v1/voices/ws__design-1:publish"))
            self.assertEqual(json.loads(publish.body), {"displayName": "harmonicfitness Coach Owen",
                                                        "description": "A man in his forties.",
                                                        "tags": ["harmonicfitness"]})
            self.module("inworld").save(dict(out[0], draft_id="a/b"), "Coach Owen")
            self.assertEqual(fake.requests[-1].path, "/voices/v1/voices/a%2Fb:publish")
        table(self, [("fish", fish), ("elevenlabs", elevenlabs), ("gemini", gemini), ("inworld", inworld)])

    def test_delete(self):
        """True on the service's 2xx, True on a 404 (already gone), an error otherwise; an edited ID stays one
        path segment."""
        for service, path, gone_status in (("fish", "/model/{id}", 204), ("elevenlabs", "/v1/voices/{id}", 200),
                                           ("gemini", "/v1beta/voices/{id}", 200),
                                           ("inworld", "/voices/v1/voices/{id}", 200)):
            with self.subTest(service):
                module = self.module(service)
                fake = self.serve(service, lambda r, s=gone_status: (s, {}, b"" if s == 204 else b"{}"))
                self.assertTrue(module.delete("voice-9"))
                self.assertEqual((fake.requests[0].method, fake.requests[0].path), ("DELETE", path.format(id="voice-9")))
                self.assertNotIn(SECRET, fake.requests[0].path)
                fake.answer = lambda r: (404, {}, b'{"message": "not found"}')
                self.assertTrue(module.delete("voice-9"))
                fake.answer = lambda r: (401, {}, b'{"message": "Invalid api key"}')
                with self.assertRaises(cloud.ServiceError) as e:
                    module.delete("voice-9")
                self.assertEqual(e.exception.kind, "auth")
                fake.requests.clear()
                fake.answer = lambda r: (200, {}, b"{}")
                module.delete("../a/b?c")
                self.assertEqual(fake.requests[0].path, path.format(id="..%2Fa%2Fb%3Fc"))

    def test_balance(self):
        def fish():
            fake = self.serve("fish", lambda r: (200, {}, json.dumps({"_id": "x", "user_id": "u",
                                                                      "credit": "12.5031"}).encode()))
            self.assertEqual(self.module("fish").balance(), {"usd": 12.5031})
            req = fake.requests[0]
            self.assertEqual((req.method, req.path), ("GET", "/wallet/self/api-credit"))
            self.assertEqual(req.headers["authorization"], f"Bearer {SECRET}")
            for body in ({"credit": "lots"}, {}, {"credit": "nan"}):   # not a number: a refusal
                self.serve("fish", lambda r, body=body: (200, {}, json.dumps(body).encode()))
                with self.assertRaises(cloud.ServiceError) as got:
                    self.module("fish").balance()
                self.assertEqual(got.exception.kind, "bad_request")

        def elevenlabs():
            fake = self.serve("elevenlabs", lambda r: (200, {}, json.dumps({
                "character_count": 2120, "character_limit": 30000, "next_character_count_reset_unix": 1793000000}).encode()))
            self.assertEqual(self.module("elevenlabs").balance(), {"used": 2120, "limit": 30000, "resets": 1793000000})
            req = fake.requests[0]
            self.assertEqual((req.method, req.path), ("GET", "/v1/user/subscription"))
            self.assertEqual(req.headers["xi-api-key"], SECRET)
            self.serve("elevenlabs", lambda r: (401, {}, b'{"detail": {"message": "missing_permissions"}}'))
            with self.assertRaises(cloud.ServiceError) as got:
                self.module("elevenlabs").balance()
            self.assertEqual(got.exception.kind, "auth")

        def openrouter():   # credits less usage
            fake = self.serve("openrouter", openrouter_answer)
            self.assertEqual(self.module("openrouter").balance(), {"usd": 17.5})
            self.assertEqual(fake.requests[-1].method, "GET")
            self.serve("openrouter", lambda r: (200, {}, b'{"data": {"total_credits": "x"}}'))
            with self.assertRaises(cloud.ServiceError):
                self.module("openrouter").balance()

        def only_what_can_say_and_has_a_key():
            import balances
            fake = self.serve("fish", lambda r: (200, {}, b'{"credit": "12.5"}'))
            with mock.patch("keys.is_set", lambda s: s in ("fish", "gemini")):
                rows = balances.balances()
            self.assertEqual(list(rows), list(cloud.SERVICES))
            self.assertEqual(rows["fish"]["usd"], 12.5)
            self.assertTrue(rows["fish"]["ok"])
            self.assertEqual(rows["gemini"], {"name": "Gemini", "billing_page": "https://aistudio.google.com/billing",
                                              "set": True, "reports": False})
            self.assertNotIn("ok", rows["elevenlabs"])   # no key: never asked
            self.assertEqual(len(fake.requests), 1)
            for row in rows.values():
                self.assertTrue(row["billing_page"].startswith("https://"))
        table(self, [("fish", fish), ("elevenlabs", elevenlabs), ("openrouter", openrouter),
                     ("balances", only_what_can_say_and_has_a_key)])


class UnreadableAnswers(unittest.TestCase):
    """A 2xx answer that isn't what a service documents stops as a ServiceError, never a traceback, and never
    becomes audio that is cached, paid for once and replayed in every build."""

    def setUp(self):
        import keys
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        env = {var: SECRET for var in keys.SERVICE_VARS.values()}
        env["HARMONICFITNESS_RETRY_WAIT"] = "0"
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)

    def serve(self, body):
        fake = FakeService(lambda r: (200, {"Content-Type": "application/json"}, body))
        fake.__enter__()
        self.addCleanup(fake.__exit__)
        for service in ("fish", "elevenlabs", "gemini", "inworld"):
            patch = mock.patch.dict(os.environ, {f"HARMONICFITNESS_{service.upper()}_URL": fake.url})
            patch.start()
            self.addCleanup(patch.stop)

    def test_every_design_save_and_speech_refuses_a_bad_body(self):
        import importlib
        for body in (b"<html>oops</html>", b"[1, 2]", b"", b"\xff\xfe"):
            with self.assertRaises(cloud.ServiceError) as got:
                cloud.json_answer(body, "fish")
            self.assertEqual(got.exception.kind, "bad_request")
        self.assertEqual(cloud.json_answer(b'{"a": 1}', "fish"), {"a": 1})
        with self.assertRaises(cloud.ServiceError):
            cloud.b64_audio("not base64!", "fish")
        # a message, a page or a blip in place of audio is refused, never cached as a clip
        for data, kw in ((b'{"detail": {"message": "quota exceeded"}}', {"expect": "pcm", "content_type": "audio/pcm"}),
                         (b"<!DOCTYPE html><html><body>Bad gateway</body></html>", {"expect": "pcm"}),
                         (b"\x1f\x8b\x08\x00" + bytes(20000), {"expect": "wav"}),
                         (tone_wav(0.05), {})):
            with self.subTest(data=data[:12]), self.assertRaises(cloud.ServiceError) as got:
                cloud.audio_pcm(data, service="fish", **kw)
            self.assertEqual(got.exception.kind, "bad_request")
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
        self.assertIn("harmonicfitness Coach Maya", str(got.exception))


class CloudRender(unittest.TestCase):
    """render.run with a web coach, in this process against fake services, as ./harmonicfitness build calls it once
    the lint and the menu pass (those are tested in test_tools). The encode is stood in for: no ffmpeg."""

    def setUp(self):
        import render
        self.render = render
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.home = os.path.join(self.d, "me")
        shutil.copytree(os.path.join(ROOT, "me.example"), self.home)
        folder = persona_home(self.home)
        for service in COACHES:
            web_coach(folder, service)
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(helpers.home(self.home))
        stack.enter_context(mock.patch.object(render, "preflight", return_value="ffmpeg"))
        stack.enter_context(mock.patch.object(render, "encode", side_effect=self.fake_encode))
        with open(DRAFT, encoding="utf-8") as f:
            self.text = f.read()

    @staticmethod
    def fake_encode(pcm, out, title):
        with open(out, "wb") as f:
            f.write(b"an mp3")

    def render_on(self, service, url, out=None, max_chars=None):
        """Returns (exit code, stdout, stderr)."""
        import context
        import draft
        import keys
        env = {var: "" for var in keys.SERVICE_VARS.values()}
        env.update({f"HARMONICFITNESS_{service.upper()}_URL": url, keys.SERVICE_VARS[service]: SECRET,
                    "HARMONICFITNESS_RETRY_WAIT": "0"})

        def main():
            p = personas.lookup(COACHES[service])
            voice = personas.voice_for(p, coachpick.pick(context.render_preferences(), p))
            self.render.run(draft.parse(self.text), voice, out or os.path.join(self.d, "x.mp3"), DRAFT,
                            hashlib.sha256(self.text.encode("utf-8")).hexdigest(), max_chars=max_chars)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.run(main)
        return code, stdout.getvalue(), stderr.getvalue()

    def set_ceiling(self, n):
        prof = os.path.join(self.home, "profile.md")
        with open(prof, encoding="utf-8") as f:
            text = f.read()
        with open(prof, "w", encoding="utf-8") as f:
            f.write(text.replace("+++\n", f"+++\ncloud_max_chars = {n}\n", 1))

    def builds(self):
        try:
            with open(os.path.join(self.home, "workouts", ".logs", "builds.jsonl"), encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]
        except OSError:
            return []

    def cached(self):
        return glob.glob(os.path.join(self.home, "workouts", ".audio-cache", "*.pcm"))

    def test_a_refused_key_exits_4(self):
        with FakeService(lambda r: (401, {}, b'{"detail": {"message": "Invalid API key"}}')) as fake:
            code, out, err = self.render_on("elevenlabs", fake.url)
        self.assertEqual(code, cli.SERVICE, out + err)
        self.assertIn("ElevenLabs", out)
        self.assertNotIn("Traceback", out + err)
        self.assertFalse(any(r.path == "/v1/voices/add" for r in fake.requests))
        with FakeService(lambda r: (401, {}, b'{"message": "Invalid api key"}')) as fake:
            code, out, err = self.render_on("fish", fake.url)
        self.assertEqual(code, cli.SERVICE, out + err)
        self.assertIn("Fish Audio", out + err)
        self.assertIn("./harmonicfitness keys", out + err)

    def test_a_broken_answer_stops_sending_and_caches_nothing(self):
        with FakeService(lambda r: (200, {"Content-Type": "application/json"}, b'{"status": "queued"}')) as fake:
            code, out, err = self.render_on("fish", fake.url)
        self.assertEqual(code, cli.ISSUES, out + err)
        self.assertLessEqual(len(fake.requests), 6)   # the queued paragraphs were never sent
        self.assertEqual(self.cached(), [])

    def test_both_ceilings_stop_before_sending(self):
        """The render checks the build's allowance against what it is about to send (the clips not cached yet):
        the lower of cloud_max_chars and --max-chars wins, and is the one named."""
        with FakeService(wav_answer) as fake:
            code, out, err = self.render_on("fish", fake.url, max_chars=10)
            self.assertEqual(code, cli.ISSUES, out + err)
            self.assertIn("--max-chars", err)
            self.assertNotIn("cloud_max_chars", err)
            self.set_ceiling(10)
            code, out, err = self.render_on("fish", fake.url)
            self.assertEqual(code, cli.ISSUES, out + err)
            self.assertIn("cloud_max_chars", err)   # an error: on stderr, through cli.run
            code, out, err = self.render_on("fish", fake.url, max_chars=5000)
            self.assertIn("cloud_max_chars", err)
            self.assertNotIn("--max-chars", err)
        self.assertEqual(fake.requests, [])

    def test_the_key_never_reaches_records_logs_or_cache_keys(self):
        import keys
        for service in ("fish", "elevenlabs", "gemini", "inworld"):
            with self.subTest(service=service):
                mp3 = os.path.join(self.d, f"{service}.mp3")
                with FakeService(every_service_answer) as fake:
                    code, out, err = self.render_on(service, fake.url, mp3)
                self.assertEqual(code, 0, out + err)
                self.assertTrue(fake.requests)
                self.assertFalse(any(SECRET in r.path or SECRET.encode() in r.body for r in fake.requests))
                texts = [out, err]
                for path in glob.glob(os.path.join(self.d, "*.build.json")) + \
                        glob.glob(os.path.join(self.home, "workouts", ".logs", "*")) + \
                        glob.glob(os.path.join(self.home, "coaches", "*", "*.json")):
                    with open(path, encoding="utf-8") as f:
                        texts.append(f.read())
                self.assertFalse(any(SECRET in t for t in texts))
                with open(os.path.splitext(mp3)[0] + ".build.json", encoding="utf-8") as f:
                    record = json.load(f)
                self.assertEqual(record["route"], service)
                self.assertGreater(record["chars_sent"], 100)
                self.assertIn("usd_estimate", record)
                var = keys.SERVICE_VARS[service]
                with mock.patch.dict(os.environ, {var: SECRET}), mock.patch.object(self.render, "check_pace_file"):
                    a = self.render.prepare_voice(coachpick.resolve(COACHES[service], None))[1]("Hello.")
                    with mock.patch.dict(os.environ, {var: "another-key"}):
                        b = self.render.prepare_voice(coachpick.resolve(COACHES[service], None))[1]("Hello.")
                self.assertEqual(a, b)

    def test_the_cost_is_printed_before_sending(self):
        with FakeService(every_service_answer) as fake:
            code, out, err = self.render_on("gemini", fake.url, os.path.join(self.d, "g.mp3"))
        self.assertEqual(code, 0, out + err)
        lines = out.splitlines()
        at = next(i for i, l in enumerate(lines) if l.startswith("Sending"))
        self.assertLess(at, next(i for i, l in enumerate(lines) if l.lstrip().startswith("[1/")))
        chars = int(lines[at].split()[1].replace(",", ""))
        self.assertEqual(cloud.rate("gemini", "gemini-3.8-flash-tts"), 13.5)
        self.assertIn(f"about ${chars * 13.5 / 1e6:.2f}", lines[at])
        self.assertIn("Gemini", lines[at])

    def test_what_was_sent_is_recorded_and_nothing_else(self):
        with FakeService(wav_answer) as fake:
            code, out, err = self.render_on("fish", fake.url, max_chars=10)
        self.assertEqual(code, cli.ISSUES, out + err)
        self.assertEqual(self.builds(), [])   # sent nothing: no line (the first web build is still to come)
        state = {"ok": 2}

        def answer(req):
            state["ok"] -= 1
            return wav_answer(req) if state["ok"] >= 0 else (401, {}, b'{"message": "Invalid api key"}')
        with FakeService(answer) as fake:
            code, out, err = self.render_on("fish", fake.url)
        self.assertEqual(code, cli.SERVICE, out + err)
        rec = self.builds()[-1]   # stopped partway: what it sent is on record
        self.assertTrue(rec["failed"])
        self.assertEqual(rec["route"], "fish")
        self.assertGreater(rec["chars_sent"], 0)
        self.assertGreaterEqual(rec["chars_sent"], rec["chars_rendered"])
        self.assertIn("usd_estimate", rec)
        self.assertFalse(os.path.exists(os.path.join(self.d, "x.build.json")))   # no MP3, no record beside it
        self.assertNotIn(SECRET, json.dumps(rec))

    def test_an_interrupted_build_resumes_without_resending(self):
        state = {"ok": 3}

        def answer(req):
            if state["ok"] <= 0:
                return 503, {}, b"{}"
            state["ok"] -= 1
            return wav_answer(req)
        with FakeService(answer) as fake:
            code, first, err = self.render_on("fish", fake.url)
            self.assertNotEqual(code, 0)
            self.assertEqual(len(self.cached()), 3)
            sent_first = len([r for r in fake.requests if r.path == "/v1/tts"])
            state["ok"] = 1000
            code, second, err = self.render_on("fish", fake.url)
        self.assertEqual(code, 0, second + err)
        first_to_render = int(first.split(" to render")[0].split()[-1])
        sent_second = len([r for r in fake.requests if r.path == "/v1/tts"]) - sent_first
        to_render = int(second.split(" to render")[0].split()[-1])
        self.assertEqual(to_render, first_to_render - 3)
        self.assertEqual(sent_second, to_render)
        self.assertIn("Sending", second)


class Deadline(unittest.TestCase):
    """cloud.request's deadline: every try and wait together, so a slow service can't hold the render lock."""

    def test_a_slow_service_runs_out_of_time_and_a_wait_past_the_deadline_is_not_slept(self):
        import time

        def slow(req):
            time.sleep(0.45)   # well past the deadline
            return wav_answer(req)
        with FakeService(slow) as fake, mock.patch.dict(os.environ, {"HARMONICFITNESS_RETRY_WAIT": "0"}):
            started = time.monotonic()
            with self.assertRaises(cloud.ServiceError) as got:
                cloud.request("POST", fake.url + "/v1/tts", {}, b"{}", timeout=30, service="fish", deadline=0.1)
            took = time.monotonic() - started
        self.assertEqual(got.exception.kind, "unavailable")
        self.assertIn("no answer within 0.1s", str(got.exception))
        self.assertLess(took, 0.4)
        slept = []
        with FakeService(lambda r: (503, {"Retry-After": "5"}, b'{"message": "busy"}')) as fake, \
                mock.patch.dict(os.environ, {"HARMONICFITNESS_RETRY_WAIT": "1"}):
            with self.assertRaises(cloud.ServiceError) as got:
                cloud.request("POST", fake.url + "/v1/tts", {}, b"{}", service="fish", deadline=2,
                              sleep=slept.append)
        self.assertEqual(slept, [])
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(got.exception.kind, "unavailable")
        self.assertIn("busy", str(got.exception))


class Scrubbing(unittest.TestCase):
    def test_a_refusal_is_scrubbed_before_it_is_cut(self):
        import keys
        body = ("x" * 290 + SECRET + " more").encode()
        with mock.patch.dict(os.environ, {keys.SERVICE_VARS["fish"]: SECRET}):
            message = cloud._message(body)
        self.assertNotIn(SECRET[:8], message)
        self.assertIn("<key", message)


class RenderCloudStops(unittest.TestCase):
    """render.render_cloud in process, with a fake service behind engines.speaker."""

    def setUp(self):
        import render
        self.render = render
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.voice = {"name": "Test", "service": "fish", "model": "s2.1-pro", "concurrency": 1, "max_chars": 0,
                      "engine": "fish", "backend": "cloud"}
        self.sent = {"chars": 0, "started": 0, "usd": 0.0}
        self.todo = [f"Line number {i}, and go." for i in range(10)]
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(render, "record_rate"))
        self.out = stack.enter_context(mock.patch("sys.stdout", new_callable=io.StringIO))

    def cache_path(self, text):
        return os.path.join(self.d, f"{abs(hash(text))}.pcm")

    def go(self, say):
        import engines
        with mock.patch.object(engines, "speaker", return_value=say):
            self.render.render_cloud(self.voice, self.todo, self.todo, 42, self.cache_path, self.sent)

    def test_unavailable_in_a_row_stops_sending(self):
        calls = []

        def always(text, seed, **kw):
            calls.append(text)
            raise cloud.ServiceError("unavailable", "fish", "couldn't reach the service (timed out)")
        with self.assertRaises(errors.RenderStopped) as got:
            self.go(always)
        self.assertEqual(len(calls), self.render.BREAKER)
        self.assertIn("in a row", str(got.exception))
        self.assertEqual(got.exception.exit_code, cli.ISSUES)
        calls.clear()

        def every_other(text, seed, **kw):
            calls.append(text)
            if len(calls) % 2:
                raise cloud.ServiceError("unavailable", "fish", "busy (HTTP 503)")
            return tone_pcm(0.3)
        with self.assertRaises(errors.RenderStopped) as got:
            self.go(every_other)
        self.assertEqual(len(calls), len(self.todo))   # never three in a row: every line was tried, then it stops
        self.assertIn("busy", str(got.exception))
        self.assertEqual(len(glob.glob(os.path.join(self.d, "*.pcm"))), len(self.todo) // 2)

    def test_an_engine_bug_is_not_an_issue_to_fix(self):
        def say(text, seed, **kw):
            raise TypeError("a bug")
        with self.assertRaises(TypeError):
            self.go(say)
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertEqual(cli.run(lambda: self.go(say)), cli.BUG)
        self.assertIn("TypeError: a bug", err.getvalue())

    def test_ctrl_c_after_sending_says_what_was_sent(self):
        calls = []

        def say(text, seed, **kw):
            calls.append(text)
            if len(calls) == 2:
                raise KeyboardInterrupt
            return tone_pcm(0.3)
        with self.assertRaises(KeyboardInterrupt):
            self.go(say)
        chars = len(self.todo[0]) + len(self.todo[1])
        self.assertIn(f"Interrupted: {chars:,} characters sent to Fish Audio; 1 clips cached; a rerun sends only "
                      "the rest.", self.out.getvalue())


if __name__ == "__main__":
    unittest.main()
